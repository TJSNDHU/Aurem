import { useState, useMemo, useEffect, createContext, useContext } from "react";
import axios from "axios";
import { useAdminBrand } from "./useAdminBrand";

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Theme context for sub-components
const CRMThemeContext = createContext(null);
const useCRMTheme = () => useContext(CRMThemeContext);

const FONT_DISPLAY = "'Cormorant Garamond', Georgia, serif";
const FONT_MONO = "'JetBrains Mono', 'Courier New', monospace";

// ─── BRAND THEME (Dynamic) ───────────────────────────────────────────────────────
const getThemeColors = (isLaVela) => isLaVela ? {
  bg: "#0D4D4D", surface: "#1A6B6B", surfaceAlt: "#1A6B6B40", surfaceHover: "#1A6B6B80",
  border: "#D4A57440", borderLight: "#D4A57430",
  gold: "#D4A574", goldDim: "#E6BE8A", goldFaint: "rgba(212,165,116,0.15)",
  green: "#72B08A", red: "#E07070", amber: "#E8A860", blue: "#7AAEC8", purple: "#9878D0",
  text: "#FDF8F5", textDim: "#D4A574", textMuted: "#E8C4B8", white: "#FDF8F5",
} : {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF2F4", surfaceHover: "#FEF2F4",
  border: "#F0E8E8", borderLight: "#E8DEE0",
  gold: "#F8A5B8", goldDim: "#E8889A", goldFaint: "rgba(248,165,184,0.08)",
  green: "#72B08A", red: "#E07070", amber: "#E8A860", blue: "#7AAEC8", purple: "#9B8ABF",
  text: "#2D2A2E", textDim: "#8A8490", textMuted: "#C4BAC0", white: "#2D2A2E",
};

// Dynamic CSS generator
const generateCss = (C) => `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=JetBrains+Mono:wght@300;400;500&display=swap');
  .crm-module * { box-sizing: border-box; margin: 0; padding: 0; }
  .crm-module ::-webkit-scrollbar { width: 3px; height: 3px; }
  .crm-module ::-webkit-scrollbar-track { background: ${C.bg}; }
  .crm-module ::-webkit-scrollbar-thumb { background: ${C.borderLight}; border-radius: 2px; }
  @keyframes crmFadeUp { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
  @keyframes crmPulse { 0%,100%{opacity:1;} 50%{opacity:.35;} }
  .crm-hover-row:hover { background: ${C.surfaceAlt} !important; }
  .crm-hover-btn:hover { opacity:.75; transform:translateY(-1px); }
  .crm-hover-card:hover { border-color: ${C.goldDim}40 !important; }
  .crm-module input:focus, .crm-module select:focus, .crm-module textarea:focus { outline:none; border-color:${C.goldDim}!important; }
  .crm-tab-btn:hover { color:${C.gold}!important; }
`;

// Style generators (receive C as parameter)
const getStatusColor = (C) => (s) => ({ "On Track": C.green, "Due Soon": C.amber, "Overdue": C.red, "Lapsed": C.blue }[s] || C.textDim);
const getTierColor = (C) => (t) => ({ VIP: C.gold, Regular: C.textDim, New: C.blue }[t] || C.textDim);
const getCycleBarColor = (C) => (day) => day >= 35 ? C.red : day >= 25 ? C.amber : C.green;
const getInputStyle = (C) => ({ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text, padding: "0.6rem 0.75rem", fontSize: "0.8rem", fontFamily: FONT_MONO });
const getBtnPrimary = (C) => ({ background: C.gold, color: C.bg, border: "none", padding: "0.6rem 1.4rem", fontSize: "0.65rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: FONT_MONO, transition: "all 0.2s" });
const getBtnSecondary = (C) => ({ background: "transparent", color: C.textDim, border: `1px solid ${C.border}`, padding: "0.6rem 1.4rem", fontSize: "0.65rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: FONT_MONO, transition: "all 0.2s" });
const getBtnGhost = (C) => ({ background: "transparent", color: C.textDim, border: "none", padding: "0.35rem 0.7rem", fontSize: "0.62rem", letterSpacing: "0.1em", cursor: "pointer", fontFamily: FONT_MONO, transition: "all 0.2s" });

// ─── DATA ─────────────────────────────────────────────────────────────────────
const today = new Date();
const daysAgo = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return d.toISOString().split("T")[0]; };
const daysFromNow = (n) => { const d = new Date(today); d.setDate(d.getDate() + n); return d.toISOString().split("T")[0]; };

const INITIAL_CUSTOMERS = [
  { id: "C001", name: "Madeleine Rousseau", email: "m.rousseau@gmail.com", phone: "+1 (416) 555-0182", city: "Toronto, ON", tier: "VIP", totalSpend: 847, orders: 6, lastPurchase: daysAgo(24), lastProduct: "PDRN Repair Serum 30ml", cycleDay: 24, nextDue: daysFromNow(4), status: "Due Soon", tags: ["PDRN", "Serum"], notes: "Skin sensitivity — avoid fragrance. Loves clinical results.", avatar: "MR" },
  { id: "C002", name: "James Whitfield", email: "jwhitfield@outlook.com", phone: "+1 (604) 555-0341", city: "Vancouver, BC", tier: "Regular", totalSpend: 312, orders: 3, lastPurchase: daysAgo(31), lastProduct: "PDRN Eye Recovery 15ml", cycleDay: 31, nextDue: daysAgo(3), status: "Overdue", tags: ["Eye", "PDRN"], notes: "Bought for wife. Usually reorders same SKU.", avatar: "JW" },
  { id: "C003", name: "Sofia Andrade", email: "sofia.a@icloud.com", phone: "+1 (514) 555-0729", city: "Montréal, QC", tier: "VIP", totalSpend: 1240, orders: 9, lastPurchase: daysAgo(18), lastProduct: "PDRN Repair Serum 30ml", cycleDay: 18, nextDue: daysFromNow(10), status: "On Track", tags: ["PDRN", "Serum", "Cream"], notes: "Aesthetician — recommends to clients. Bulk discount inquiry.", avatar: "SA" },
  { id: "C004", name: "Daniel Park", email: "dpark.skin@gmail.com", phone: "+1 (416) 555-0554", city: "Toronto, ON", tier: "New", totalSpend: 89, orders: 1, lastPurchase: daysAgo(8), lastProduct: "Barrier Restore Cream 50ml", cycleDay: 8, nextDue: daysFromNow(20), status: "On Track", tags: ["Cream", "First-Time"], notes: "First order. Referred by Sofia Andrade.", avatar: "DP" },
  { id: "C005", name: "Priya Sharma", email: "priya.sharma@rogers.com", phone: "+1 (905) 555-0198", city: "Mississauga, ON", tier: "Regular", totalSpend: 534, orders: 4, lastPurchase: daysAgo(26), lastProduct: "PDRN Repair Serum 30ml", cycleDay: 26, nextDue: daysFromNow(2), status: "Due Soon", tags: ["PDRN", "Serum"], notes: "Very responsive to email. Morning routine user.", avatar: "PS" },
  { id: "C006", name: "Chloé Tremblay", email: "chloe.t@videotron.ca", phone: "+1 (418) 555-0867", city: "Québec City, QC", tier: "Regular", totalSpend: 445, orders: 3, lastPurchase: daysAgo(45), lastProduct: "PDRN Ampoule 10x2ml", cycleDay: 45, nextDue: daysAgo(17), status: "Lapsed", tags: ["Ampoule"], notes: "3 orders but 45 days since last. Win-back candidate.", avatar: "CT" },
  { id: "C007", name: "Ahmed Hassan", email: "a.hassan@telus.net", phone: "+1 (780) 555-0423", city: "Edmonton, AB", tier: "VIP", totalSpend: 1890, orders: 14, lastPurchase: daysAgo(22), lastProduct: "PDRN Repair Serum 30ml", cycleDay: 22, nextDue: daysFromNow(6), status: "Due Soon", tags: ["PDRN", "Serum", "Eye"], notes: "Highest LTV customer. Skincare enthusiast. Responds to new launches.", avatar: "AH" },
  { id: "C008", name: "Natalie Bergeron", email: "n.bergeron@shaw.ca", phone: "+1 (403) 555-0612", city: "Calgary, AB", tier: "New", totalSpend: 178, orders: 2, lastPurchase: daysAgo(5), lastProduct: "Barrier Restore Cream 50ml", cycleDay: 5, nextDue: daysFromNow(23), status: "On Track", tags: ["Cream", "New"], notes: "Second order within 2 weeks. High engagement.", avatar: "NB" },
];

const AUTOMATIONS = [
  { id: "A001", name: "Day 25 Repurchase Nudge", trigger: "25 days after purchase", channel: "Email", status: "Active", sent: 142, opened: 89, converted: 34, product: "PDRN Repair Serum 30ml" },
  { id: "A002", name: "Day 28 Cart Recovery", trigger: "28 days — no reorder", channel: "Email + SMS", status: "Active", sent: 98, opened: 61, converted: 19, product: "All PDRN SKUs" },
  { id: "A003", name: "Day 35 Win-Back", trigger: "35 days — still no reorder", channel: "Email", status: "Active", sent: 56, opened: 28, converted: 8, product: "All SKUs — 10% offer" },
  { id: "A004", name: "New Customer Welcome", trigger: "1 hour after first order", channel: "Email", status: "Active", sent: 203, opened: 167, converted: 0, product: "Education sequence" },
  { id: "A005", name: "VIP Early Access", trigger: "New product launch", channel: "Email + SMS", status: "Draft", sent: 0, opened: 0, converted: 0, product: "All new launches" },
];

const TIMELINE = [
  { day: 1, label: "Welcome", action: "Send welcome email with PDRN education guide", type: "email" },
  { day: 3, label: "Check-in", action: "How to apply — technique tips SMS", type: "sms" },
  { day: 7, label: "Week 1", action: "What to expect at 7 days — set expectations", type: "email" },
  { day: 14, label: "Midpoint", action: "Progress check-in — before/after prompt", type: "email" },
  { day: 21, label: "Results", action: "Results should be visible — social share prompt", type: "email" },
  { day: 25, label: "Nudge", action: "Running low? Reorder now — personalized message", type: "email", highlight: true },
  { day: 28, label: "Cycle End", action: "Repurchase reminder + bundle offer", type: "email+sms", highlight: true },
  { day: 35, label: "Win-Back", action: "10% loyalty discount — limited time", type: "email" },
  { day: 45, label: "Re-engage", action: "New formula update or product education", type: "email" },
];

// ─── SMALL COMPONENTS (Brand-Aware) ─────────────────────────────────────────────
function Avatar({ initials, tier }) {
  const C = useCRMTheme();
  const tierColor = getTierColor(C);
  const bg = tier === "VIP" ? "rgba(200,169,110,0.15)" : tier === "New" ? "rgba(74,138,200,0.12)" : "rgba(100,100,120,0.15)";
  const col = tierColor(tier);
  return (
    <div style={{ width: 36, height: 36, borderRadius: "50%", background: bg, border: `1px solid ${col}30`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.65rem", color: col, fontFamily: FONT_MONO, letterSpacing: "0.05em", flexShrink: 0 }}>
      {initials}
    </div>
  );
}

function CycleBar({ day, size = "normal" }) {
  const C = useCRMTheme();
  const cycleBarColor = getCycleBarColor(C);
  const pct = Math.min(100, (day / 45) * 100);
  const color = cycleBarColor(day);
  const h = size === "small" ? 3 : 4;
  return (
    <div style={{ position: "relative" }}>
      <div style={{ height: h, background: C.border, borderRadius: 2, overflow: "hidden", position: "relative" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.6s ease" }} />
        <div style={{ position: "absolute", top: 0, left: `${(28 / 45) * 100}%`, width: 1, height: "100%", background: C.borderLight }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.25rem" }}>
        <span style={{ fontSize: "0.55rem", color: C.textMuted, fontFamily: FONT_MONO }}>Day {day}</span>
        <span style={{ fontSize: "0.55rem", color: C.textMuted, fontFamily: FONT_MONO }}>28-day cycle</span>
      </div>
    </div>
  );
}

function Badge({ label, color, faint }) {
  return (
    <span style={{ fontSize: "0.55rem", letterSpacing: "0.15em", color, border: `1px solid ${color}`, padding: "0.12rem 0.45rem", fontFamily: FONT_MONO, background: faint ? `${color}15` : "transparent", whiteSpace: "nowrap" }}>
      {label}
    </span>
  );
}

function Modal({ title, children, onClose, wide }) {
  const C = useCRMTheme();
  const btnGhost = getBtnGhost(C);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.88)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: C.surface, border: `1px solid ${C.borderLight}`, width: wide ? "min(780px,96vw)" : "min(560px,96vw)", maxHeight: "90vh", overflowY: "auto", animation: "crmFadeUp 0.2s ease" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1.1rem 1.5rem", borderBottom: `1px solid ${C.border}` }}>
          <span style={{ fontFamily: FONT_DISPLAY, fontSize: "1.1rem", color: C.white, fontWeight: 400 }}>{title}</span>
          <button onClick={onClose} style={{ ...btnGhost, fontSize: "1.3rem", color: C.textDim }}>×</button>
        </div>
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
}

function FormField({ label, children }) {
  const C = useCRMTheme();
  return (
    <div style={{ marginBottom: "1rem" }}>
      <label style={{ display: "block", fontSize: "0.58rem", letterSpacing: "0.2em", color: C.textDim, textTransform: "uppercase", marginBottom: "0.35rem", fontFamily: FONT_MONO }}>{label}</label>
      {children}
    </div>
  );
}

// ─── OVERVIEW TAB ─────────────────────────────────────────────────────────────
function OverviewTab({ customers, onSelect }) {
  const C = useCRMTheme();
  const statusColor = getStatusColor(C);
  const tierColor = getTierColor(C);
  const btnPrimary = getBtnPrimary(C);
  
  const dueSoon = customers.filter(c => c.status === "Due Soon").length;
  const overdue = customers.filter(c => c.status === "Overdue").length;
  const lapsed = customers.filter(c => c.status === "Lapsed").length;
  const onTrack = customers.filter(c => c.status === "On Track").length;
  const totalLTV = customers.reduce((s, c) => s + c.totalSpend, 0);
  const avgLTV = Math.round(totalLTV / customers.length);

  const urgentCustomers = customers.filter(c => c.status === "Due Soon" || c.status === "Overdue").sort((a, b) => b.cycleDay - a.cycleDay);

  return (
    <div style={{ animation: "crmFadeUp 0.3s ease" }}>
      {/* KPI Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1px", background: C.border, marginBottom: "2rem" }}>
        {[
          { label: "Total Customers", val: customers.length, sub: "in CRM", col: C.gold },
          { label: "Due Soon", val: dueSoon, sub: "days 24–28", col: C.amber, pulse: true },
          { label: "Overdue", val: overdue, sub: "past day 28", col: C.redBright, pulse: overdue > 0 },
          { label: "Lapsed", val: lapsed, sub: "45+ days", col: C.blueBright },
          { label: "Avg. LTV", val: `$${avgLTV}`, sub: "per customer", col: C.gold },
        ].map((k, i) => (
          <div key={i} style={{ background: C.surface, padding: "1.1rem 1.25rem", animation: `crmFadeUp 0.3s ${i * 0.05}s both` }}>
            <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "0.4rem" }}>{k.label}</div>
            <div style={{ fontSize: "1.7rem", color: k.col, fontFamily: FONT_DISPLAY, fontWeight: 300, lineHeight: 1 }}>{k.val}</div>
            <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FONT_MONO, marginTop: "0.3rem" }}>{k.sub}</div>
            {k.pulse && k.val > 0 && <div style={{ width: 5, height: 5, borderRadius: "50%", background: k.col, marginTop: "0.4rem", animation: "crmPulse 1.5s infinite", boxShadow: `0 0 6px ${k.col}` }} />}
          </div>
        ))}
      </div>

      {/* Action Required */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ fontSize: "0.62rem", letterSpacing: "0.3em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "1rem" }}>⚡ Action Required Today</div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          {urgentCustomers.map((c, i) => (
            <div key={c.id} className="crm-hover-card" onClick={() => onSelect(c)}
              style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "0.9rem 1.1rem", background: C.surface, border: `1px solid ${C.border}`, cursor: "pointer", transition: "all 0.2s", animation: `crmFadeUp 0.3s ${i * 0.06}s both`, flexWrap: "wrap" }}
              data-testid={`urgent-customer-${c.id}`}>
              <Avatar initials={c.avatar} tier={c.tier} />
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                  <span style={{ fontFamily: FONT_DISPLAY, fontSize: "0.95rem", color: C.white }}>{c.name}</span>
                  <Badge label={c.tier} color={tierColor(c.tier)} />
                  <Badge label={c.status.toUpperCase()} color={statusColor(c.status)} faint />
                </div>
                <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO, marginTop: "0.2rem" }}>
                  Last: {c.lastProduct} · {c.city}
                </div>
              </div>
              <div style={{ width: 140 }}>
                <CycleBar day={c.cycleDay} size="small" />
              </div>
              <div style={{ display: "flex", gap: "0.4rem" }}>
                <button style={{ ...btnPrimary, padding: "0.35rem 0.75rem", fontSize: "0.58rem" }} className="crm-hover-btn"
                  onClick={e => { e.stopPropagation(); }}>
                  Send Reminder
                </button>
              </div>
            </div>
          ))}
          {urgentCustomers.length === 0 && (
            <div style={{ padding: "2rem", textAlign: "center", color: C.textMuted, fontFamily: FONT_MONO, fontSize: "0.72rem" }}>
              ✓ No urgent actions — all customers on track
            </div>
          )}
        </div>
      </div>

      {/* Cycle Stage Distribution */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1px", background: C.border }}>
        <div style={{ background: C.surface, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.62rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "1rem" }}>Cycle Stage Distribution</div>
          {[
            { label: "On Track (Day 1–23)", count: onTrack, color: C.greenBright },
            { label: "Due Soon (Day 24–28)", count: dueSoon, color: C.amber },
            { label: "Overdue (Day 29–35)", count: overdue, color: C.redBright },
            { label: "Lapsed (Day 35+)", count: lapsed, color: C.blueBright },
          ].map(row => (
            <div key={row.label} style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
              <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO, width: 180 }}>{row.label}</div>
              <div style={{ flex: 1, height: 6, background: C.border, borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${(row.count / customers.length) * 100}%`, background: row.color, transition: "width 0.6s ease", borderRadius: 3 }} />
              </div>
              <div style={{ fontSize: "0.72rem", color: row.color, fontFamily: FONT_MONO, width: 20, textAlign: "right" }}>{row.count}</div>
            </div>
          ))}
        </div>

        <div style={{ background: C.surface, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.62rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "1rem" }}>Revenue by Tier</div>
          {[
            { tier: "VIP", customers: customers.filter(c => c.tier === "VIP") },
            { tier: "Regular", customers: customers.filter(c => c.tier === "Regular") },
            { tier: "New", customers: customers.filter(c => c.tier === "New") },
          ].map(row => {
            const rev = row.customers.reduce((s, c) => s + c.totalSpend, 0);
            return (
              <div key={row.tier} style={{ marginBottom: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <span style={{ fontSize: "0.65rem", color: tierColor(row.tier), fontFamily: FONT_MONO }}>{row.tier} ({row.customers.length})</span>
                  <span style={{ fontSize: "0.65rem", color: C.gold, fontFamily: FONT_MONO }}>${rev.toLocaleString()}</span>
                </div>
                <div style={{ height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(rev / totalLTV) * 100}%`, background: tierColor(row.tier), borderRadius: 2, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── CUSTOMERS TAB ────────────────────────────────────────────────────────────
function CustomersTab({ customers, onSelect, onAdd }) {
  const C = useCRMTheme();
  const statusColor = getStatusColor(C);
  const tierColor = getTierColor(C);
  const inputStyle = getInputStyle(C);
  const btnPrimary = getBtnPrimary(C);
  const btnGhost = getBtnGhost(C);
  
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => customers.filter(c => {
    const matchSearch = c.name.toLowerCase().includes(search.toLowerCase()) || c.email.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "All" || filter === "" || c.status === filter || c.tier === filter;
    return matchSearch && matchFilter;
  }), [customers, search, filter]);

  return (
    <div style={{ animation: "crmFadeUp 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search customers..." style={{ ...inputStyle, width: 220, padding: "0.5rem 0.75rem" }} data-testid="crm-search" />
          <select value={filter} onChange={e => setFilter(e.target.value)} style={{ ...inputStyle, width: 150 }} data-testid="crm-filter">
            {["All", "VIP", "Regular", "New", "Due Soon", "Overdue", "Lapsed", "On Track"].map(f => <option key={f}>{f}</option>)}
          </select>
        </div>
        <button style={btnPrimary} className="crm-hover-btn" onClick={onAdd} data-testid="add-customer-btn">+ Add Customer</button>
      </div>

      {/* Table */}
      <div style={{ border: `1px solid ${C.border}`, overflow: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2.5fr 1.8fr 1.2fr 1fr 1.8fr 1.2fr 100px", padding: "0.6rem 1rem", borderBottom: `1px solid ${C.border}`, background: C.bg, minWidth: "900px" }}>
          {["Customer", "Email", "Tier", "Orders", "28-Day Cycle", "Status", ""].map(h => (
            <div key={h} style={{ fontSize: "0.56rem", letterSpacing: "0.2em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO }}>{h}</div>
          ))}
        </div>

        {filtered.map((c, i) => (
          <div key={c.id} className="crm-hover-row" onClick={() => onSelect(c)}
            style={{ display: "grid", gridTemplateColumns: "2.5fr 1.8fr 1.2fr 1fr 1.8fr 1.2fr 100px", padding: "0.8rem 1rem", borderBottom: `1px solid ${C.border}`, background: i % 2 === 0 ? C.surface : "transparent", cursor: "pointer", transition: "background 0.15s", animation: `crmFadeUp 0.3s ${i * 0.03}s both`, minWidth: "900px" }}
            data-testid={`customer-row-${c.id}`}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <Avatar initials={c.avatar} tier={c.tier} />
              <div>
                <div style={{ fontFamily: FONT_DISPLAY, fontSize: "0.9rem", color: C.white }}>{c.name}</div>
                <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: FONT_MONO, marginTop: "0.1rem" }}>{c.city}</div>
              </div>
            </div>
            <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FONT_MONO, alignSelf: "center" }}>{c.email}</div>
            <div style={{ alignSelf: "center" }}><Badge label={c.tier} color={tierColor(c.tier)} /></div>
            <div style={{ fontSize: "0.78rem", color: C.text, fontFamily: FONT_MONO, alignSelf: "center" }}>{c.orders}</div>
            <div style={{ alignSelf: "center", paddingRight: "1rem" }}><CycleBar day={c.cycleDay} size="small" /></div>
            <div style={{ alignSelf: "center" }}><Badge label={c.status.toUpperCase()} color={statusColor(c.status)} faint /></div>
            <div style={{ alignSelf: "center" }}>
              <button style={btnGhost} className="crm-hover-btn" onClick={e => { e.stopPropagation(); onSelect(c); }}>View →</button>
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding: "0.75rem 1rem", fontSize: "0.62rem", color: C.textMuted, fontFamily: FONT_MONO }}>
        Showing {filtered.length} of {customers.length} customers
      </div>
    </div>
  );
}

// ─── CUSTOMER PROFILE MODAL ───────────────────────────────────────────────────
function CustomerProfile({ customer: c, onClose }) {
  const C = useCRMTheme();
  const statusColor = getStatusColor(C);
  const tierColor = getTierColor(C);
  const cycleBarColor = getCycleBarColor(C);
  const btnGhost = getBtnGhost(C);
  const btnPrimary = getBtnPrimary(C);
  const inputStyle = getInputStyle(C);
  
  const [tab, setTab] = useState("profile");

  const repurchaseMsg = () => {
    if (c.status === "Overdue") return `Hi ${c.name.split(" ")[0]}, your PDRN serum should be running out — don't lose your progress! Reorder now and we'll have it to you in 2 days.`;
    if (c.status === "Due Soon") return `Hi ${c.name.split(" ")[0]}, you're on day ${c.cycleDay} of your PDRN cycle — results compound with consistency. Ready to reorder your ${c.lastProduct}?`;
    if (c.status === "Lapsed") return `Hi ${c.name.split(" ")[0]}, we noticed it's been a while since your last order. Your skin's regeneration cycle benefits from consistent PDRN use — here's 10% off to restart.`;
    return `Hi ${c.name.split(" ")[0]}, enjoying your ${c.lastProduct}? You're on day ${c.cycleDay} of your cycle — results are just getting started!`;
  };

  return (
    <Modal title={`${c.name} · Customer Profile`} onClose={onClose} wide>
      {/* Profile Header */}
      <div style={{ display: "flex", gap: "1.25rem", alignItems: "flex-start", marginBottom: "1.5rem", padding: "1rem", background: C.bg, border: `1px solid ${C.border}`, flexWrap: "wrap" }}>
        <Avatar initials={c.avatar} tier={c.tier} />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", marginBottom: "0.4rem" }}>
            <span style={{ fontFamily: FONT_DISPLAY, fontSize: "1.2rem", color: C.white }}>{c.name}</span>
            <Badge label={c.tier} color={tierColor(c.tier)} />
            <Badge label={c.status.toUpperCase()} color={statusColor(c.status)} faint />
          </div>
          <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO }}>{c.email} · {c.phone} · {c.city}</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
          {[["Total Spend", `$${c.totalSpend}`], ["Orders", c.orders], ["LTV Score", c.tier === "VIP" ? "A+" : c.tier === "Regular" ? "B" : "C"]].map(([k, v]) => (
            <div key={k} style={{ textAlign: "center" }}>
              <div style={{ fontSize: "0.55rem", color: C.textMuted, fontFamily: FONT_MONO, letterSpacing: "0.15em", textTransform: "uppercase" }}>{k}</div>
              <div style={{ fontSize: "1.1rem", color: C.gold, fontFamily: FONT_DISPLAY, fontWeight: 300 }}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 28-day cycle visual */}
      <div style={{ padding: "1rem", background: C.bg, border: `1px solid ${C.border}`, marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "0.75rem" }}>28-Day Repurchase Cycle</div>
        <div style={{ position: "relative", height: 20, background: C.border, borderRadius: 3, overflow: "hidden", marginBottom: "0.5rem" }}>
          <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: `${Math.min(100, (c.cycleDay / 45) * 100)}%`, background: cycleBarColor(c.cycleDay), transition: "width 0.8s ease", borderRadius: 3 }} />
          <div style={{ position: "absolute", top: 0, left: `${(28 / 45) * 100}%`, width: 1, height: "100%", background: "rgba(255,255,255,0.2)" }} />
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.58rem", color: C.textMuted, fontFamily: FONT_MONO }}>
          <span>Day 1</span><span style={{ color: C.amber }}>Day 25 (nudge)</span><span style={{ color: C.amber }}>Day 28 ↑</span><span>Day 45</span>
        </div>
        <div style={{ marginTop: "0.5rem", fontSize: "0.68rem", color: cycleBarColor(c.cycleDay), fontFamily: FONT_MONO }}>
          Currently Day {c.cycleDay} · Last product: {c.lastProduct}
        </div>
      </div>

      {/* Profile Tabs */}
      <div style={{ display: "flex", gap: 0, borderBottom: `1px solid ${C.border}`, marginBottom: "1.25rem" }}>
        {[["profile", "Profile"], ["message", "Send Message"], ["notes", "Notes"]].map(([id, label]) => (
          <button key={id} className="crm-tab-btn" onClick={() => setTab(id)}
            style={{ ...btnGhost, borderBottom: `2px solid ${tab === id ? C.gold : "transparent"}`, color: tab === id ? C.gold : C.textDim, padding: "0.6rem 1rem", letterSpacing: "0.1em" }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "profile" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          {[["Customer ID", c.id], ["Last Purchase", c.lastPurchase], ["Next Due", c.nextDue], ["Tags", c.tags.join(", ")]].map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: "0.58rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "0.25rem" }}>{k}</div>
              <div style={{ fontSize: "0.8rem", color: C.text, fontFamily: FONT_MONO }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {tab === "message" && (
        <div>
          <div style={{ padding: "1rem", background: C.bg, border: `1px solid ${C.border}`, marginBottom: "1rem" }}>
            <div style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FONT_MONO, marginBottom: "0.5rem", letterSpacing: "0.15em", textTransform: "uppercase" }}>AI-Generated Message · {c.status}</div>
            <div style={{ fontSize: "0.82rem", color: C.text, fontFamily: FONT_DISPLAY, lineHeight: 1.7, fontStyle: "italic" }}>{repurchaseMsg()}</div>
          </div>
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button style={btnPrimary} className="crm-hover-btn">Send via Email</button>
            <button style={btnSecondary} className="crm-hover-btn">Send via SMS</button>
          </div>
        </div>
      )}

      {tab === "notes" && (
        <div>
          <div style={{ padding: "1rem", background: C.bg, border: `1px solid ${C.border}`, marginBottom: "1rem", fontSize: "0.82rem", color: C.text, fontFamily: FONT_DISPLAY, lineHeight: 1.7 }}>
            {c.notes}
          </div>
          <textarea style={{ ...inputStyle, height: 80 }} placeholder="Add new note..." />
          <div style={{ marginTop: "0.75rem" }}>
            <button style={btnPrimary} className="crm-hover-btn">Save Note</button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ─── AUTOMATIONS TAB ──────────────────────────────────────────────────────────
function AutomationsTab() {
  const C = useCRMTheme();
  const btnPrimary = getBtnPrimary(C);
  
  return (
    <div style={{ animation: "crmFadeUp 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <div style={{ fontFamily: FONT_DISPLAY, fontSize: "1.3rem", color: C.white, fontWeight: 300 }}>Repurchase Automations</div>
          <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO, marginTop: "0.2rem" }}>28-day cycle triggers — set once, run forever</div>
        </div>
        <button style={btnPrimary} className="crm-hover-btn">+ New Automation</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1px", background: C.border, marginBottom: "2rem", overflow: "auto" }}>
        {AUTOMATIONS.map((a, i) => {
          const rate = a.sent > 0 ? Math.round((a.converted / a.sent) * 100) : 0;
          return (
            <div key={a.id} style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 2.5fr 80px", alignItems: "center", padding: "1rem 1.25rem", background: i % 2 === 0 ? C.surface : C.bg, animation: `crmFadeUp 0.3s ${i * 0.06}s both`, minWidth: "800px" }}>
              <div>
                <div style={{ fontFamily: FONT_DISPLAY, fontSize: "0.95rem", color: C.white }}>{a.name}</div>
                <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FONT_MONO, marginTop: "0.2rem" }}>{a.product}</div>
              </div>
              <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO }}>{a.trigger}</div>
              <div><Badge label={a.channel} color={C.blueBright} /></div>
              <div style={{ display: "flex", gap: "1.5rem" }}>
                {[["Sent", a.sent], ["Opened", a.opened], ["Converted", a.converted]].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: "0.56rem", color: C.textMuted, fontFamily: FONT_MONO, letterSpacing: "0.1em" }}>{k}</div>
                    <div style={{ fontSize: "0.9rem", color: k === "Converted" ? C.gold : C.text, fontFamily: FONT_MONO }}>{v}</div>
                  </div>
                ))}
                {a.sent > 0 && (
                  <div>
                    <div style={{ fontSize: "0.56rem", color: C.textMuted, fontFamily: FONT_MONO, letterSpacing: "0.1em" }}>Conv. Rate</div>
                    <div style={{ fontSize: "0.9rem", color: rate >= 20 ? C.greenBright : C.amber, fontFamily: FONT_MONO }}>{rate}%</div>
                  </div>
                )}
              </div>
              <div><Badge label={a.status.toUpperCase()} color={a.status === "Active" ? C.greenBright : C.textDim} faint /></div>
            </div>
          );
        })}
      </div>

      {/* 28-Day Timeline */}
      <div>
        <div style={{ fontSize: "0.62rem", letterSpacing: "0.3em", color: C.textMuted, textTransform: "uppercase", fontFamily: FONT_MONO, marginBottom: "1.25rem" }}>28-Day Customer Journey Map</div>
        <div style={{ position: "relative", paddingLeft: "2rem" }}>
          <div style={{ position: "absolute", left: "0.75rem", top: 0, bottom: 0, width: 1, background: C.border }} />
          {TIMELINE.map((t, i) => (
            <div key={i} style={{ display: "flex", gap: "1rem", marginBottom: "0.85rem", animation: `crmFadeUp 0.3s ${i * 0.04}s both` }}>
              <div style={{ position: "relative", zIndex: 1, width: 28, height: 28, borderRadius: "50%", background: t.highlight ? C.gold : C.surface, border: `1px solid ${t.highlight ? C.gold : C.border}`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginLeft: "-0.75rem" }}>
                <span style={{ fontSize: "0.58rem", color: t.highlight ? C.bg : C.textDim, fontFamily: FONT_MONO, fontWeight: t.highlight ? 500 : 300 }}>{t.day}</span>
              </div>
              <div style={{ padding: "0.6rem 0.85rem", background: t.highlight ? C.goldFaint : C.surface, border: `1px solid ${t.highlight ? C.goldDim : C.border}`, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.2rem", flexWrap: "wrap" }}>
                  <span style={{ fontFamily: FONT_DISPLAY, fontSize: "0.85rem", color: t.highlight ? C.gold : C.white }}>{t.label}</span>
                  <Badge label={t.type.toUpperCase()} color={t.type.includes("sms") ? C.blueBright : C.textDim} />
                </div>
                <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FONT_MONO }}>{t.action}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── ADD CUSTOMER MODAL ───────────────────────────────────────────────────────
function AddCustomerModal({ onClose, onAdd }) {
  const C = useCRMTheme();
  const inputStyle = getInputStyle(C);
  const btnPrimary = getBtnPrimary(C);
  const btnSecondary = getBtnSecondary(C);
  
  const [form, setForm] = useState({ tier: "New", cycleDay: "1" });
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = () => {
    if (!form.name || !form.email) return;
    const initials = form.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
    onAdd({
      id: `C${String(Date.now()).slice(-4)}`,
      name: form.name, email: form.email, phone: form.phone || "—",
      city: form.city || "Canada", tier: form.tier, totalSpend: 0, orders: 1,
      lastPurchase: daysAgo(parseInt(form.cycleDay) || 1),
      lastProduct: form.product || "PDRN Repair Serum 30ml",
      cycleDay: parseInt(form.cycleDay) || 1,
      nextDue: daysFromNow(28 - (parseInt(form.cycleDay) || 1)),
      status: parseInt(form.cycleDay) >= 35 ? "Lapsed" : parseInt(form.cycleDay) >= 25 ? "Due Soon" : "On Track",
      tags: [form.tier], notes: form.notes || "", avatar: initials,
    });
    onClose();
  };

  return (
    <Modal title="Add Customer" onClose={onClose}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 1rem" }}>
        <div style={{ gridColumn: "1/-1" }}>
          <FormField label="Full Name *"><input style={inputStyle} value={form.name || ""} onChange={e => set("name", e.target.value)} placeholder="Madeleine Rousseau" data-testid="customer-name-input" /></FormField>
        </div>
        <FormField label="Email *"><input style={inputStyle} value={form.email || ""} onChange={e => set("email", e.target.value)} placeholder="email@example.com" data-testid="customer-email-input" /></FormField>
        <FormField label="Phone"><input style={inputStyle} value={form.phone || ""} onChange={e => set("phone", e.target.value)} placeholder="+1 (416) 555-0000" /></FormField>
        <FormField label="City"><input style={inputStyle} value={form.city || ""} onChange={e => set("city", e.target.value)} placeholder="Toronto, ON" /></FormField>
        <FormField label="Tier"><select style={inputStyle} value={form.tier} onChange={e => set("tier", e.target.value)}>
          {["New", "Regular", "VIP"].map(t => <option key={t}>{t}</option>)}
        </select></FormField>
        <FormField label="Last Product Purchased"><select style={inputStyle} value={form.product || ""} onChange={e => set("product", e.target.value)}>
          <option value="">Select SKU...</option>
          {["PDRN Repair Serum 30ml", "PDRN Eye Recovery 15ml", "Barrier Restore Cream 50ml", "PDRN Ampoule 10x2ml", "Peptide Firming Concentrate 30ml"].map(p => <option key={p}>{p}</option>)}
        </select></FormField>
        <div style={{ gridColumn: "1/-1" }}>
          <FormField label="Current Cycle Day (days since last purchase)">
            <input style={inputStyle} type="number" min="1" max="90" value={form.cycleDay} onChange={e => set("cycleDay", e.target.value)} placeholder="1" />
          </FormField>
        </div>
        <div style={{ gridColumn: "1/-1" }}>
          <FormField label="Notes"><textarea style={{ ...inputStyle, height: 70 }} value={form.notes || ""} onChange={e => set("notes", e.target.value)} placeholder="Skin sensitivity, preferences, referral source..." /></FormField>
        </div>
      </div>
      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.5rem" }}>
        <button style={btnSecondary} onClick={onClose}>Cancel</button>
        <button style={btnPrimary} className="crm-hover-btn" onClick={handleSubmit} data-testid="save-customer-btn">Add Customer</button>
      </div>
    </Modal>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function CRMRepurchaseCycle() {
  const { isLaVela, shortName, fullName } = useAdminBrand();
  const C = getThemeColors(isLaVela);
  const css = generateCss(C);
  
  const [activeTab, setActiveTab] = useState("overview");
  const [customers, setCustomers] = useState(INITIAL_CUSTOMERS);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  // Load customers from backend
  useEffect(() => {
    const fetchCustomers = async () => {
      try {
        const token = localStorage.getItem('reroots_token');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const activeBrand = localStorage.getItem('admin_active_brand') || 'reroots';
        const res = await axios.get(`${API}/admin/customers?brand=${activeBrand}`, { headers });
        if (res.data?.length) {
          // Transform real customers to match CRM format
          const transformedCustomers = res.data.slice(0, 20).map((c, idx) => {
            const daysSincePurchase = c.last_order_date 
              ? Math.floor((new Date() - new Date(c.last_order_date)) / (1000 * 60 * 60 * 24))
              : 30;
            const status = daysSincePurchase >= 35 ? "Lapsed" : daysSincePurchase >= 25 ? "Due Soon" : daysSincePurchase >= 28 ? "Overdue" : "On Track";
            const tier = c.total_spent >= 500 ? "VIP" : c.total_spent >= 100 ? "Regular" : "New";
            const initials = (c.first_name?.[0] || '') + (c.last_name?.[0] || '');
            
            return {
              id: c.id || `C${idx}`,
              name: `${c.first_name || ''} ${c.last_name || ''}`.trim() || c.email?.split('@')[0] || 'Customer',
              email: c.email || '',
              phone: c.phone || '—',
              city: c.city ? `${c.city}, ${c.province || ''}` : 'Canada',
              tier,
              totalSpend: c.total_spent || 0,
              orders: c.order_count || 0,
              lastPurchase: c.last_order_date?.split('T')[0] || daysAgo(30),
              lastProduct: "PDRN Repair Serum 30ml",
              cycleDay: daysSincePurchase,
              nextDue: daysFromNow(28 - daysSincePurchase),
              status,
              tags: [tier],
              notes: c.notes || '',
              avatar: initials || 'XX'
            };
          });
          setCustomers(transformedCustomers);
        }
      } catch (err) {
        console.log('Using initial CRM data');
      }
    };
    fetchCustomers();
  }, []);

  const tabs = [
    { id: "overview", label: "Overview", icon: "◈" },
    { id: "customers", label: `Customers (${customers.length})`, icon: "◎" },
    { id: "automations", label: "Automations", icon: "◉" },
  ];

  const dueSoon = customers.filter(c => c.status === "Due Soon" || c.status === "Overdue").length;

  const handleAddCustomer = async (customer) => {
    setCustomers(prev => [...prev, customer]);
    try {
      const token = localStorage.getItem('reroots_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      await axios.post(`${API}/admin/customers`, customer, { headers });
    } catch (err) {
      console.log('Saved locally');
    }
  };

  return (
    <CRMThemeContext.Provider value={C}>
      <div className="crm-module" style={{ minHeight: "100vh", background: C.bg, fontFamily: FONT_DISPLAY, color: C.text }} data-testid="crm-repurchase-cycle">
        <style>{css}</style>

        {/* Header */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "1.1rem 2rem", display: "flex", alignItems: "center", justifyContent: "space-between", background: isLaVela ? "linear-gradient(180deg,#0A3C3C 0%,transparent 100%)" : "linear-gradient(180deg,#0c0e14 0%,transparent 100%)", flexWrap: "wrap", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "1rem", flexWrap: "wrap" }}>
            <span style={{ fontFamily: FONT_DISPLAY, fontSize: "1.4rem", letterSpacing: "0.2em", color: C.gold, fontWeight: 300 }}>{shortName}</span>
            <span style={{ fontSize: "0.56rem", letterSpacing: "0.35em", color: C.textMuted, fontFamily: FONT_MONO, textTransform: "uppercase" }}>CRM · Module 02 · 28-Day Cycle Engine</span>
          </div>
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
            {dueSoon > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.62rem", color: C.amber, fontFamily: FONT_MONO }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.amber, animation: "crmPulse 1.5s infinite" }} />
                {dueSoon} customer{dueSoon > 1 ? "s" : ""} need attention
              </div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.62rem", color: C.green, fontFamily: FONT_MONO, letterSpacing: "0.1em" }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.green, animation: "crmPulse 2s infinite", boxShadow: `0 0 6px ${C.green}` }} />
              CYCLE ENGINE ACTIVE
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 2rem", display: "flex", overflowX: "auto" }}>
          {tabs.map(t => (
            <button key={t.id} className="crm-tab-btn" onClick={() => setActiveTab(t.id)}
              style={{ background: "none", border: "none", borderBottom: `2px solid ${activeTab === t.id ? C.gold : "transparent"}`, padding: "0.85rem 1.1rem", cursor: "pointer", color: activeTab === t.id ? C.gold : C.textDim, fontSize: "0.68rem", letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: FONT_MONO, transition: "all 0.2s", display: "flex", alignItems: "center", gap: "0.4rem", whiteSpace: "nowrap" }}
              data-testid={`crm-tab-${t.id}`}>
              <span style={{ opacity: 0.7 }}>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: "2rem" }}>
          {activeTab === "overview" && <OverviewTab customers={customers} onSelect={setSelectedCustomer} />}
          {activeTab === "customers" && <CustomersTab customers={customers} onSelect={setSelectedCustomer} onAdd={() => setShowAddModal(true)} />}
          {activeTab === "automations" && <AutomationsTab />}
        </div>

        {/* Module Roadmap Footer */}
        <div style={{ borderTop: `1px solid ${C.border}`, padding: "0.85rem 2rem", display: "flex", gap: "1.5rem", background: C.surface, flexWrap: "wrap" }}>
          {[
            { label: "01 · Inventory", done: true },
            { label: "02 · CRM", active: true },
            { label: "03 · Orders", done: false },
            { label: "04 · Accounting", done: false },
          ].map(m => (
            <div key={m.label} style={{ fontSize: "0.58rem", letterSpacing: "0.15em", color: m.active ? C.gold : m.done ? C.green : C.textMuted, fontFamily: FONT_MONO, textTransform: "uppercase", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              {m.active && <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.gold, animation: "crmPulse 2s infinite" }} />}
              {m.done && !m.active && <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.green }} />}
              {m.label}
            </div>
          ))}
        </div>

        {/* Modals */}
        {selectedCustomer && <CustomerProfile customer={selectedCustomer} onClose={() => setSelectedCustomer(null)} />}
        {showAddModal && <AddCustomerModal onClose={() => setShowAddModal(false)} onAdd={handleAddCustomer} />}
      </div>
    </CRMThemeContext.Provider>
  );
}
