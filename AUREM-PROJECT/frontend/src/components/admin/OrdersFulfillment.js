import { useState, useMemo, useEffect, createContext, useContext } from "react";
import axios from "axios";
import { useAdminBrand } from "./useAdminBrand";

const API = ((typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Theme context for sub-components
const OrdersThemeContext = createContext(null);
const useOrdersTheme = () => useContext(OrdersThemeContext);

const FD = "'Cormorant Garamond', Georgia, serif";
const FM = "'JetBrains Mono', 'Courier New', monospace";

// ─── BRAND THEME (Dynamic) ───────────────────────────────────────────────────────
const getThemeColors = (isLaVela) => isLaVela ? {
  bg: "#0D4D4D", surface: "#1A6B6B", surfaceAlt: "#1A6B6B40",
  border: "#D4A57440", borderLight: "#D4A57430",
  gold: "#D4A574", goldDim: "#E6BE8A", goldFaint: "rgba(212,165,116,0.15)",
  green: "#72B08A", greenBright: "#72B08A", greenFaint: "rgba(114,176,138,0.15)",
  red: "#E07070", redBright: "#E07070", redFaint: "rgba(224,112,112,0.15)",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.15)",
  blue: "#7AAEC8", blueBright: "#7AAEC8", blueFaint: "rgba(122,174,200,0.15)",
  purple: "#9878D0", purpleBright: "#9878D0",
  text: "#FDF8F5", textDim: "#D4A574", textMuted: "#E8C4B8",
  white: "#FDF8F5",
} : {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceAlt: "#FEF2F4",
  border: "#F0E8E8", borderLight: "#E8DEE0",
  gold: "#F8A5B8", goldDim: "#E8889A", goldFaint: "rgba(248,165,184,0.08)",
  green: "#72B08A", greenBright: "#72B08A", greenFaint: "rgba(114,176,138,0.08)",
  red: "#E07070", redBright: "#E07070", redFaint: "rgba(224,112,112,0.08)",
  amber: "#E8A860", amberFaint: "rgba(232,168,96,0.08)",
  blue: "#7AAEC8", blueBright: "#7AAEC8", blueFaint: "rgba(122,174,200,0.08)",
  purple: "#9B8ABF", purpleBright: "#9B8ABF",
  text: "#2D2A2E", textDim: "#8A8490", textMuted: "#C4BAC0",
  white: "#2D2A2E",
};

// Dynamic CSS generator
const generateCss = (C) => `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300&family=JetBrains+Mono:wght@300;400&display=swap');
  .orders-module *{box-sizing:border-box;margin:0;padding:0;}
  .orders-module ::-webkit-scrollbar{width:3px;height:3px;}
  .orders-module ::-webkit-scrollbar-track{background:${C.bg};}
  .orders-module ::-webkit-scrollbar-thumb{background:${C.borderLight};border-radius:2px;}
  @keyframes ordersFadeUp{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
  @keyframes ordersPulse{0%,100%{opacity:1;}50%{opacity:.3;}}
  .orders-hr:hover{background:${C.surfaceAlt}!important;cursor:pointer;}
  .orders-hb:hover{opacity:.75;transform:translateY(-1px);}
  .orders-module input:focus,.orders-module select:focus,.orders-module textarea:focus{outline:none;border-color:${C.goldDim}!important;}
`;

// Dynamic style generators
const getInputStyle = (C) => ({ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text, padding: "0.58rem 0.75rem", fontSize: "0.78rem", fontFamily: FM });
const getBtnPrimary = (C) => ({ background: C.gold, color: C.bg, border: "none", padding: "0.58rem 1.3rem", fontSize: "0.62rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: FM, transition: "all 0.2s" });
const getBtnSecondary = (C) => ({ background: "transparent", color: C.textDim, border: `1px solid ${C.border}`, padding: "0.58rem 1.3rem", fontSize: "0.62rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: FM, transition: "all 0.2s" });
const getBtnGhost = (C) => ({ background: "transparent", color: C.textDim, border: "none", padding: "0.3rem 0.6rem", fontSize: "0.6rem", cursor: "pointer", fontFamily: FM });

// Dynamic status meta
const getStatusMeta = (C) => ({
  Processing: { color: C.amber, bg: C.amberFaint, icon: "⧖" },
  Shipped: { color: C.blueBright, bg: C.blueFaint, icon: "◈" },
  Fulfilled: { color: C.blueBright, bg: C.blueFaint, icon: "◈" },
  Delivered: { color: C.greenBright, bg: C.greenFaint, icon: "✓" },
  Refunded: { color: C.textDim, bg: "transparent", icon: "↩" },
  Cancelled: { color: C.redBright, bg: C.redFaint, icon: "✕" },
});

// ─── DATA ─────────────────────────────────────────────────────────────────────
const today = new Date();
const dA = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return d.toISOString().split("T")[0]; };
const fDate = (s) => new Date(s).toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" });
const fCur = (n) => `$${Number(n).toLocaleString("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const INITIAL_ORDERS = [
  { id: "RR-10042", customer: "Ahmed Hassan", email: "a.hassan@telus.net", city: "Edmonton, AB", date: dA(0), items: [{ sku: "PDRN Repair Serum 30ml", qty: 2, price: 129 }, { sku: "PDRN Eye Recovery 15ml", qty: 1, price: 89 }], subtotal: 347, tax: 17.35, shipping: 0, total: 364.35, status: "Processing", fulfillment: "Unfulfilled", carrier: null, tracking: null, notes: "VIP — expedite", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10041", customer: "Priya Sharma", email: "priya.sharma@rogers.com", city: "Mississauga, ON", date: dA(1), items: [{ sku: "PDRN Repair Serum 30ml", qty: 1, price: 129 }], subtotal: 129, tax: 16.77, shipping: 9.99, total: 155.76, status: "Processing", fulfillment: "Unfulfilled", carrier: null, tracking: null, notes: "", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10040", customer: "Sofia Andrade", email: "sofia.a@icloud.com", city: "Montréal, QC", date: dA(2), items: [{ sku: "PDRN Repair Serum 30ml", qty: 3, price: 129 }, { sku: "Barrier Restore Cream 50ml", qty: 2, price: 98 }], subtotal: 583, tax: 86.09, shipping: 0, total: 669.09, status: "Fulfilled", fulfillment: "Fulfilled", carrier: "Canada Post", tracking: "7356291048CA", notes: "Aesthetician bulk order", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10039", customer: "Madeleine Rousseau", email: "m.rousseau@gmail.com", city: "Toronto, ON", date: dA(3), items: [{ sku: "PDRN Repair Serum 30ml", qty: 1, price: 129 }], subtotal: 129, tax: 16.77, shipping: 0, total: 145.77, status: "Shipped", fulfillment: "Fulfilled", carrier: "Purolator", tracking: "PRX7291048", notes: "", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10038", customer: "Daniel Park", email: "dpark.skin@gmail.com", city: "Toronto, ON", date: dA(5), items: [{ sku: "Barrier Restore Cream 50ml", qty: 1, price: 98 }], subtotal: 98, tax: 12.74, shipping: 9.99, total: 120.73, status: "Delivered", fulfillment: "Fulfilled", carrier: "Canada Post", tracking: "6234819204CA", notes: "First order", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10037", customer: "James Whitfield", email: "jwhitfield@outlook.com", city: "Vancouver, BC", date: dA(7), items: [{ sku: "PDRN Eye Recovery 15ml", qty: 1, price: 89 }], subtotal: 89, tax: 4.45, shipping: 0, total: 93.45, status: "Delivered", fulfillment: "Fulfilled", carrier: "Purolator", tracking: "PRX7104829", notes: "", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10036", customer: "Chloé Tremblay", email: "chloe.t@videotron.ca", city: "Québec City, QC", date: dA(10), items: [{ sku: "PDRN Ampoule 10x2ml", qty: 2, price: 149 }], subtotal: 298, tax: 44.07, shipping: 0, total: 342.07, status: "Delivered", fulfillment: "Fulfilled", carrier: "Canada Post", tracking: "7102938401CA", notes: "", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10035", customer: "Natalie Bergeron", email: "n.bergeron@shaw.ca", city: "Calgary, AB", date: dA(12), items: [{ sku: "Barrier Restore Cream 50ml", qty: 1, price: 98 }, { sku: "PDRN Repair Serum 30ml", qty: 1, price: 129 }], subtotal: 227, tax: 11.35, shipping: 0, total: 238.35, status: "Delivered", fulfillment: "Fulfilled", carrier: "Canada Post", tracking: "6209184730CA", notes: "", channel: "Website", paymentStatus: "Paid" },
  { id: "RR-10034", customer: "Marcus Lee", email: "marcus.lee@hotmail.com", city: "Toronto, ON", date: dA(14), items: [{ sku: "PDRN Repair Serum 30ml", qty: 1, price: 129 }], subtotal: 129, tax: 16.77, shipping: 9.99, total: 155.76, status: "Refunded", fulfillment: "Returned", carrier: "Canada Post", tracking: "6108374920CA", notes: "Customer said wrong product ordered", channel: "Website", paymentStatus: "Refunded" },
];

const CARRIERS = ["Canada Post", "Purolator", "FedEx", "UPS", "Canpar"];
const PROVINCES = { ON: 0.13, BC: 0.12, AB: 0.05, QC: 0.14975, MB: 0.12, SK: 0.11, NS: 0.15, NB: 0.15, NL: 0.15, PE: 0.15 };

// ─── SHARED UI ────────────────────────────────────────────────────────────────
function Badge({ label, color, bg }) {
  return <span style={{ fontSize: "0.54rem", letterSpacing: "0.15em", color, border: `1px solid ${color}40`, padding: "0.12rem 0.45rem", fontFamily: FM, background: bg || "transparent", whiteSpace: "nowrap" }}>{label}</span>;
}

function StatCard({ label, value, sub, color, pulse: p, anim }) {
  const C = useOrdersTheme();
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "1.1rem 1.3rem", animation: anim || "ordersFadeUp 0.4s ease both" }}>
      <div style={{ fontSize: "0.56rem", letterSpacing: "0.28em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.4rem" }}>{label}</div>
      <div style={{ fontSize: "1.65rem", color: color || C.gold, fontFamily: FD, fontWeight: 300, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: FM, marginTop: "0.3rem" }}>{sub}</div>}
      {p && <div style={{ width: 5, height: 5, borderRadius: "50%", background: color, marginTop: "0.4rem", animation: "ordersPulse 1.5s infinite", boxShadow: `0 0 6px ${color}` }} />}
    </div>
  );
}

function Modal({ title, children, onClose, wide }) {
  const C = useOrdersTheme();
  const bGhost = getBtnGhost(C);
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.9)", zIndex: 300, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: C.surface, border: `1px solid ${C.borderLight}`, width: wide ? "min(860px,96vw)" : "min(580px,96vw)", maxHeight: "92vh", overflowY: "auto", animation: "ordersFadeUp 0.2s ease" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1rem 1.5rem", borderBottom: `1px solid ${C.border}` }}>
          <span style={{ fontFamily: FD, fontSize: "1.05rem", color: C.white, fontWeight: 400 }}>{title}</span>
          <button onClick={onClose} style={{ ...bGhost, fontSize: "1.2rem" }}>×</button>
        </div>
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
}

function FF({ label, children }) {
  const C = useOrdersTheme();
  return (
    <div style={{ marginBottom: "0.9rem" }}>
      <label style={{ display: "block", fontSize: "0.56rem", letterSpacing: "0.2em", color: C.textDim, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.3rem" }}>{label}</label>
      {children}
    </div>
  );
}

// ─── ORDER ROW ────────────────────────────────────────────────────────────────
function OrderRow({ order, idx, onSelect }) {
  const C = useOrdersTheme();
  const STATUS_META = getStatusMeta(C);
  const bGhost = getBtnGhost(C);
  const sm = STATUS_META[order.status] || STATUS_META.Processing;
  return (
    <div className="orders-hr" onClick={() => onSelect(order)}
      style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1.5fr 1fr 1fr 1fr 90px", padding: "0.78rem 1rem", borderBottom: `1px solid ${C.border}`, background: idx % 2 === 0 ? C.surface : "transparent", transition: "background 0.15s", animation: `ordersFadeUp 0.3s ${idx * 0.03}s both`, minWidth: "900px" }}
      data-testid={`order-row-${order.id}`}>
      <div>
        <div style={{ fontSize: "0.75rem", color: C.gold, fontFamily: FM }}>{order.id}</div>
        <div style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FM, marginTop: "0.15rem" }}>{order.channel}</div>
      </div>
      <div>
        <div style={{ fontFamily: FD, fontSize: "0.88rem", color: C.white }}>{order.customer}</div>
        <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: FM, marginTop: "0.1rem" }}>{order.city}</div>
      </div>
      <div style={{ alignSelf: "center" }}>
        <div style={{ fontSize: "0.7rem", color: C.textDim, fontFamily: FM }}>{fDate(order.date)}</div>
        <div style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FM, marginTop: "0.1rem" }}>{order.items.length} item{order.items.length > 1 ? "s" : ""}</div>
      </div>
      <div style={{ alignSelf: "center" }}>
        <div style={{ fontSize: "0.82rem", color: C.white, fontFamily: FM }}>{fCur(order.total)}</div>
        <div style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FM }}>incl. HST/GST</div>
      </div>
      <div style={{ alignSelf: "center" }}>
        <Badge label={order.status.toUpperCase()} color={sm.color} bg={sm.bg} />
      </div>
      <div style={{ alignSelf: "center" }}>
        <Badge label={order.paymentStatus.toUpperCase()} color={order.paymentStatus === "Paid" ? C.greenBright : order.paymentStatus === "Refunded" ? C.textDim : C.amber} />
      </div>
      <div style={{ alignSelf: "center", textAlign: "right" }}>
        <button style={bGhost} className="orders-hb" onClick={e => { e.stopPropagation(); onSelect(order); }}>View →</button>
      </div>
    </div>
  );
}

// ─── ORDER DETAIL MODAL ───────────────────────────────────────────────────────
function OrderDetail({ order: o, onClose, onUpdate }) {
  const [tracking, setTracking] = useState(o.tracking || "");
  const [carrier, setCarrier] = useState(o.carrier || "");
  const [status] = useState(o.status);

  const sm = STATUS_META[status] || STATUS_META.Processing;
  const province = o.city.split(", ")[1];
  const taxRate = PROVINCES[province] || 0.13;

  const handleFulfill = () => {
    if (!tracking || !carrier) return;
    onUpdate({ ...o, status: "Shipped", fulfillment: "Fulfilled", tracking, carrier });
    onClose();
  };

  return (
    <Modal title={`Order ${o.id} · ${o.customer}`} onClose={onClose} wide>
      {/* Header Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "1px", background: C.border, marginBottom: "1.5rem" }}>
        {[
          { label: "Order Total", val: fCur(o.total), col: C.gold },
          { label: "Status", val: <Badge label={status.toUpperCase()} color={sm.color} bg={sm.bg} /> },
          { label: "Payment", val: <Badge label={o.paymentStatus.toUpperCase()} color={o.paymentStatus === "Paid" ? C.greenBright : C.textDim} /> },
          { label: "Order Date", val: fDate(o.date) },
        ].map((k, i) => (
          <div key={i} style={{ background: C.bg, padding: "0.85rem 1rem" }}>
            <div style={{ fontSize: "0.54rem", letterSpacing: "0.2em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.3rem" }}>{k.label}</div>
            <div style={{ fontSize: typeof k.val === "string" ? "1.1rem" : "inherit", color: k.col || C.text, fontFamily: typeof k.val === "string" ? FD : "inherit", fontWeight: 300 }}>{k.val}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.5rem" }}>
        {/* Left — Items & Summary */}
        <div>
          <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.75rem" }}>Order Items</div>
          <div style={{ border: `1px solid ${C.border}`, marginBottom: "1rem" }}>
            {o.items.map((item, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.7rem 0.85rem", borderBottom: i < o.items.length - 1 ? `1px solid ${C.border}` : "none", background: i % 2 === 0 ? C.surface : C.bg }}>
                <div>
                  <div style={{ fontFamily: FD, fontSize: "0.85rem", color: C.white }}>{item.sku}</div>
                  <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: FM }}>Qty: {item.qty} × {fCur(item.price)}</div>
                </div>
                <div style={{ fontFamily: FM, fontSize: "0.8rem", color: C.gold }}>{fCur(item.qty * item.price)}</div>
              </div>
            ))}
          </div>

          {/* Price Breakdown */}
          <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "0.85rem" }}>
            {[
              ["Subtotal", fCur(o.subtotal)],
              [`Tax (${province} ${(taxRate * 100).toFixed(2)}%)`, fCur(o.tax)],
              ["Shipping", o.shipping === 0 ? "FREE" : fCur(o.shipping)],
            ].map(([k, v]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.4rem", fontSize: "0.68rem", color: C.textDim, fontFamily: FM }}>
                <span>{k}</span><span style={{ color: C.text }}>{v}</span>
              </div>
            ))}
            <div style={{ borderTop: `1px solid ${C.border}`, marginTop: "0.5rem", paddingTop: "0.5rem", display: "flex", justifyContent: "space-between", fontSize: "0.8rem", fontFamily: FM }}>
              <span style={{ color: C.text }}>Order Total</span>
              <span style={{ color: C.gold, fontWeight: 500 }}>{fCur(o.total)}</span>
            </div>
          </div>
        </div>

        {/* Right — Fulfillment */}
        <div>
          <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.75rem" }}>Fulfillment</div>

          <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "1rem", marginBottom: "1rem" }}>
            <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FM, marginBottom: "0.5rem" }}>Ship To</div>
            <div style={{ fontFamily: FD, fontSize: "0.95rem", color: C.white }}>{o.customer}</div>
            <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FM }}>{o.city}</div>
            <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FM }}>{o.email}</div>
          </div>

          {(o.status === "Processing" || status === "Processing") ? (
            <div>
              <FF label="Carrier">
                <select style={iStyle} value={carrier} onChange={e => setCarrier(e.target.value)} data-testid="carrier-select">
                  <option value="">Select carrier...</option>
                  {CARRIERS.map(c => <option key={c}>{c}</option>)}
                </select>
              </FF>
              <FF label="Tracking Number">
                <input style={iStyle} value={tracking} onChange={e => setTracking(e.target.value)} placeholder="e.g. 7356291048CA" data-testid="tracking-input" />
              </FF>
              <button style={{ ...bPri, width: "100%" }} className="orders-hb" onClick={handleFulfill}
                disabled={!tracking || !carrier} data-testid="fulfill-btn">
                Mark as Fulfilled & Ship
              </button>
            </div>
          ) : (
            <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "1rem" }}>
              {o.carrier && <div style={{ marginBottom: "0.5rem" }}><span style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FM, letterSpacing: "0.15em" }}>CARRIER </span><span style={{ fontSize: "0.78rem", color: C.text, fontFamily: FM }}>{o.carrier}</span></div>}
              {o.tracking && <div><span style={{ fontSize: "0.58rem", color: C.textMuted, fontFamily: FM, letterSpacing: "0.15em" }}>TRACKING </span><span style={{ fontSize: "0.78rem", color: C.blueBright, fontFamily: FM }}>{o.tracking}</span></div>}
              {!o.tracking && <div style={{ fontSize: "0.7rem", color: C.textDim, fontFamily: FM }}>No tracking info available</div>}
            </div>
          )}

          {o.notes && (
            <div style={{ marginTop: "1rem", padding: "0.75rem", background: C.goldFaint, border: `1px solid ${C.goldDim}30`, fontSize: "0.7rem", color: C.text, fontFamily: FM }}>
              📝 {o.notes}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem", paddingTop: "1rem", borderTop: `1px solid ${C.border}`, flexWrap: "wrap" }}>
        <button style={bSec} className="orders-hb" onClick={onClose}>Close</button>
        {o.status === "Delivered" && o.paymentStatus === "Paid" && (
          <button style={{ ...bSec, color: C.redBright, borderColor: `${C.redBright}40` }} className="orders-hb">Issue Refund</button>
        )}
        <button style={bPri} className="orders-hb">Print Packing Slip</button>
      </div>
    </Modal>
  );
}

// ─── CREATE ORDER MODAL ───────────────────────────────────────────────────────
function CreateOrderModal({ onClose, onAdd }) {
  const SKUS = [
    { name: "PDRN Repair Serum 30ml", price: 129 },
    { name: "PDRN Eye Recovery 15ml", price: 89 },
    { name: "Barrier Restore Cream 50ml", price: 98 },
    { name: "PDRN Ampoule 10x2ml", price: 149 },
    { name: "Peptide Firming Concentrate 30ml", price: 119 },
  ];

  const [form, setForm] = useState({ province: "ON", channel: "Manual" });
  const [items, setItems] = useState([{ sku: SKUS[0].name, qty: 1, price: SKUS[0].price }]);
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const subtotal = items.reduce((s, i) => s + i.qty * i.price, 0);
  const taxRate = PROVINCES[form.province] || 0.13;
  const tax = +(subtotal * taxRate).toFixed(2);
  const shipping = subtotal >= 150 ? 0 : 9.99;
  const total = +(subtotal + tax + shipping).toFixed(2);

  const addItem = () => setItems(prev => [...prev, { sku: SKUS[0].name, qty: 1, price: SKUS[0].price }]);
  const removeItem = (i) => setItems(prev => prev.filter((_, idx) => idx !== i));
  const updateItem = (i, key, val) => setItems(prev => prev.map((item, idx) => idx === i ? { ...item, [key]: val, ...(key === "sku" ? { price: SKUS.find(s => s.name === val)?.price || item.price } : {}) } : item));

  const handleCreate = () => {
    if (!form.customer || !form.email) return;
    const newOrder = {
      id: `RR-${10043 + Math.floor(Math.random() * 100)}`,
      customer: form.customer, email: form.email,
      city: `${form.city || "Toronto"}, ${form.province}`,
      date: today.toISOString().split("T")[0], items,
      subtotal, tax, shipping, total,
      status: "Processing", fulfillment: "Unfulfilled",
      carrier: null, tracking: null, notes: form.notes || "",
      channel: form.channel, paymentStatus: "Paid",
    };
    onAdd(newOrder); onClose();
  };

  return (
    <Modal title="Create New Order" onClose={onClose} wide>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 1.5rem" }}>
        <FF label="Customer Name *"><input style={iStyle} value={form.customer || ""} onChange={e => set("customer", e.target.value)} placeholder="Full name" data-testid="order-customer-input" /></FF>
        <FF label="Email *"><input style={iStyle} value={form.email || ""} onChange={e => set("email", e.target.value)} placeholder="email@example.com" /></FF>
        <FF label="City"><input style={iStyle} value={form.city || ""} onChange={e => set("city", e.target.value)} placeholder="Toronto" /></FF>
        <FF label="Province">
          <select style={iStyle} value={form.province} onChange={e => set("province", e.target.value)}>
            {Object.keys(PROVINCES).map(p => <option key={p}>{p}</option>)}
          </select>
        </FF>
        <FF label="Channel">
          <select style={iStyle} value={form.channel} onChange={e => set("channel", e.target.value)}>
            {["Website", "Manual", "Phone", "Wholesale", "Influencer"].map(c => <option key={c}>{c}</option>)}
          </select>
        </FF>
      </div>

      {/* Items */}
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ fontSize: "0.56rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "0.6rem" }}>Order Items</div>
        {items.map((item, i) => (
          <div key={i} style={{ display: "grid", gridTemplateColumns: "3fr 80px 100px 30px", gap: "0.5rem", marginBottom: "0.5rem", alignItems: "center" }}>
            <select style={iStyle} value={item.sku} onChange={e => updateItem(i, "sku", e.target.value)}>
              {SKUS.map(s => <option key={s.name}>{s.name}</option>)}
            </select>
            <input style={iStyle} type="number" min="1" value={item.qty} onChange={e => updateItem(i, "qty", parseInt(e.target.value) || 1)} placeholder="Qty" />
            <div style={{ ...iStyle, display: "flex", alignItems: "center", color: C.gold }}>{fCur(item.qty * item.price)}</div>
            {items.length > 1 && <button style={bGhost} onClick={() => removeItem(i)}>✕</button>}
          </div>
        ))}
        <button style={{ ...bSec, padding: "0.4rem 0.9rem", fontSize: "0.6rem" }} onClick={addItem}>+ Add Item</button>
      </div>

      {/* Summary */}
      <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "1rem", marginBottom: "1rem" }}>
        {[["Subtotal", fCur(subtotal)], [`Tax (${form.province} ${(taxRate * 100).toFixed(1)}%)`, fCur(tax)], ["Shipping", shipping === 0 ? "FREE" : fCur(shipping)]].map(([k, v]) => (
          <div key={k} style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem", fontSize: "0.68rem", color: C.textDim, fontFamily: FM }}>
            <span>{k}</span><span>{v}</span>
          </div>
        ))}
        <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: "0.5rem", marginTop: "0.5rem", display: "flex", justifyContent: "space-between", fontSize: "0.85rem", fontFamily: FM }}>
          <span style={{ color: C.text }}>Total</span><span style={{ color: C.gold }}>{fCur(total)}</span>
        </div>
      </div>

      <FF label="Notes"><textarea style={{ ...iStyle, height: 60 }} value={form.notes || ""} onChange={e => set("notes", e.target.value)} placeholder="Internal notes..." /></FF>

      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.5rem" }}>
        <button style={bSec} onClick={onClose}>Cancel</button>
        <button style={bPri} className="orders-hb" onClick={handleCreate} data-testid="create-order-btn">Create Order</button>
      </div>
    </Modal>
  );
}

// ─── ANALYTICS VIEW ───────────────────────────────────────────────────────────
function AnalyticsView({ orders }) {
  const paid = orders.filter(o => o.paymentStatus === "Paid");
  const revenue = paid.reduce((s, o) => s + o.total, 0);
  const avgOrder = revenue / (paid.length || 1);

  const byStatus = Object.keys(STATUS_META).map(s => ({
    label: s, count: orders.filter(o => o.status === s).length, color: STATUS_META[s].color
  })).filter(s => s.count > 0);

  const bySKU = {};
  orders.forEach(o => o.items.forEach(i => {
    bySKU[i.sku] = (bySKU[i.sku] || 0) + (i.qty * i.price);
  }));
  const skuRanked = Object.entries(bySKU).sort((a, b) => b[1] - a[1]);
  const maxSKU = skuRanked[0]?.[1] || 1;

  const daily = {};
  orders.filter(o => o.paymentStatus === "Paid").forEach(o => {
    daily[o.date] = (daily[o.date] || 0) + o.total;
  });
  const dailySorted = Object.entries(daily).sort((a, b) => a[0].localeCompare(b[0])).slice(-7);
  const maxDay = Math.max(...dailySorted.map(d => d[1]));

  return (
    <div style={{ animation: "ordersFadeUp 0.3s ease" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1px", background: C.border, marginBottom: "2rem" }}>
        <StatCard label="Total Revenue (14d)" value={fCur(revenue)} sub={`${paid.length} paid orders`} />
        <StatCard label="Avg Order Value" value={fCur(avgOrder)} sub="all channels" />
        <StatCard label="Units Shipped" value={paid.reduce((s, o) => s + o.items.reduce((ss, i) => ss + i.qty, 0), 0)} sub="last 14 days" color={C.greenBright} />
        <StatCard label="Refund Rate" value={`${Math.round((orders.filter(o => o.status === "Refunded").length / orders.length) * 100)}%`} sub="industry avg 3%" color={C.textDim} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1px", background: C.border, marginBottom: "2rem" }}>
        {/* Daily Revenue */}
        <div style={{ background: C.surface, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "1rem" }}>Daily Revenue (Last 7 Days)</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: "0.4rem", height: 90 }}>
            {dailySorted.map(([date, val], i) => (
              <div key={date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "0.3rem" }}>
                <div style={{ fontSize: "0.52rem", color: C.gold, fontFamily: FM }}>{val > 0 ? fCur(val).replace("$", "") : ""}</div>
                <div style={{ width: "100%", height: `${(val / maxDay) * 65}px`, background: i === dailySorted.length - 1 ? C.gold : C.goldDim, borderRadius: "1px 1px 0 0", minHeight: 4, transition: "height 0.5s ease" }} />
                <div style={{ fontSize: "0.5rem", color: C.textMuted, fontFamily: FM }}>{new Date(date).toLocaleDateString("en-CA", { month: "short", day: "numeric" })}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Revenue by SKU */}
        <div style={{ background: C.surface, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "1rem" }}>Revenue by SKU</div>
          {skuRanked.map(([sku, rev], i) => (
            <div key={sku} style={{ marginBottom: "0.65rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                <span style={{ fontSize: "0.65rem", color: C.text, fontFamily: FD }}>{sku}</span>
                <span style={{ fontSize: "0.65rem", color: C.gold, fontFamily: FM }}>{fCur(rev)}</span>
              </div>
              <div style={{ height: 3, background: C.border, borderRadius: 2 }}>
                <div style={{ height: "100%", width: `${(rev / maxSKU) * 100}%`, background: i === 0 ? C.gold : C.goldDim, borderRadius: 2, transition: "width 0.6s ease" }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Order Status Breakdown */}
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "1.25rem" }}>
        <div style={{ fontSize: "0.58rem", letterSpacing: "0.25em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM, marginBottom: "1rem" }}>Order Status Breakdown</div>
        <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
          {byStatus.map(s => (
            <div key={s.label} style={{ textAlign: "center" }}>
              <div style={{ fontSize: "1.6rem", color: s.color, fontFamily: FD, fontWeight: 300 }}>{s.count}</div>
              <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: FM, marginTop: "0.2rem" }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── MAIN ─────────────────────────────────────────────────────────────────────
export default function OrdersFulfillment() {
  const { isLaVela, shortName, fullName } = useAdminBrand();
  const C = getThemeColors(isLaVela);
  const css = generateCss(C);
  const bPri = getBtnPrimary(C);
  const iStyle = getInputStyle(C);
  
  const [orders, setOrders] = useState(INITIAL_ORDERS);
  const [activeTab, setActiveTab] = useState("orders");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const token = localStorage.getItem('reroots_token');
  const activeBrand = localStorage.getItem('admin_active_brand') || 'reroots';

  // Load orders from backend
  useEffect(() => {
    const fetchOrders = async () => {
      if (!token) return;
      try {
        const res = await axios.get(`${API}/business/fulfillment/orders?brand=${activeBrand}`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.data?.length) setOrders(res.data);
      } catch (err) {
        console.log('Using initial orders data');
      }
    };
    fetchOrders();
  }, [token, activeBrand]);

  const filtered = useMemo(() => orders.filter(o => {
    const ms = search.toLowerCase();
    const matchS = o.id.toLowerCase().includes(ms) || o.customer.toLowerCase().includes(ms) || o.city.toLowerCase().includes(ms);
    const matchF = statusFilter === "All" || o.status === statusFilter;
    return matchS && matchF;
  }), [orders, search, statusFilter]);

  const processing = orders.filter(o => o.status === "Processing").length;
  const tabs = [
    { id: "orders", label: `All Orders (${orders.length})`, icon: "◈" },
    { id: "fulfillment", label: `Needs Fulfillment (${processing})`, icon: "◉", alert: processing > 0 },
    { id: "analytics", label: "Revenue Analytics", icon: "◎" },
  ];

  const fulfillmentOrders = orders.filter(o => o.status === "Processing");

  const handleAddOrder = async (order) => {
    setOrders(prev => [order, ...prev]);
    try {
      await axios.post(`${API}/business/fulfillment/orders`, order, { headers: { Authorization: `Bearer ${token}` } });
    } catch (err) {
      console.log('Saved locally');
    }
  };

  return (
    <OrdersThemeContext.Provider value={C}>
      <div className="orders-module" style={{ minHeight: "100vh", background: C.bg, fontFamily: FD, color: C.text }} data-testid="orders-fulfillment">
        <style>{css}</style>

        {/* Header */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "1.1rem 2rem", display: "flex", alignItems: "center", justifyContent: "space-between", background: isLaVela ? "linear-gradient(180deg,#0A3C3C 0%,transparent 100%)" : "linear-gradient(180deg,#0b0c10 0%,transparent 100%)", flexWrap: "wrap", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "1rem", flexWrap: "wrap" }}>
            <span style={{ fontFamily: FD, fontSize: "1.4rem", letterSpacing: "0.2em", color: C.gold, fontWeight: 300 }}>{shortName}</span>
            <span style={{ fontSize: "0.54rem", letterSpacing: "0.35em", color: C.textMuted, fontFamily: FM, textTransform: "uppercase" }}>Orders & Fulfillment · Module 03</span>
          </div>
          <div style={{ display: "flex", gap: "1rem", alignItems: "center", flexWrap: "wrap" }}>
            {processing > 0 && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.6rem", color: C.amber, fontFamily: FM }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.amber, animation: "ordersPulse 1.5s infinite" }} />
                {processing} order{processing > 1 ? "s" : ""} awaiting fulfillment
              </div>
            )}
            <button style={bPri} className="orders-hb" onClick={() => setShowCreate(true)} data-testid="new-order-btn">+ New Order</button>
          </div>
        </div>

        {/* Quick Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "1px", background: C.border, borderBottom: `1px solid ${C.border}` }}>
          {[
            { label: "Revenue (14d)", value: fCur(orders.filter(o => o.paymentStatus === "Paid").reduce((s, o) => s + o.total, 0)), sub: "all channels" },
            { label: "Processing", value: processing, sub: "needs action", color: processing > 0 ? C.amber : C.greenBright, pulse: processing > 0 },
            { label: "Shipped", value: orders.filter(o => o.status === "Shipped").length, sub: "in transit", color: C.blueBright },
            { label: "Delivered", value: orders.filter(o => o.status === "Delivered").length, sub: "last 14 days", color: C.greenBright },
            { label: "Refunds", value: orders.filter(o => o.status === "Refunded").length, sub: "last 14 days", color: C.textDim },
          ].map((s, i) => <StatCard key={i} {...s} anim={`ordersFadeUp 0.3s ${i * 0.05}s both`} />)}
        </div>

        {/* Tabs */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 2rem", display: "flex", overflowX: "auto" }}>
          {tabs.map(t => (
            <button key={t.id} className="tab-btn" onClick={() => setActiveTab(t.id)}
            style={{ background: "none", border: "none", borderBottom: `2px solid ${activeTab === t.id ? C.gold : "transparent"}`, padding: "0.8rem 1.1rem", cursor: "pointer", color: activeTab === t.id ? C.gold : C.textDim, fontSize: "0.65rem", letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: FM, transition: "all 0.2s", display: "flex", alignItems: "center", gap: "0.4rem", whiteSpace: "nowrap" }}
            data-testid={`orders-tab-${t.id}`}>
            {t.icon} {t.label}
            {t.alert && <span style={{ width: 5, height: 5, borderRadius: "50%", background: C.amber, display: "inline-block", animation: "ordersPulse 1.5s infinite" }} />}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: "2rem" }}>
        {activeTab === "analytics" && <AnalyticsView orders={orders} />}

        {(activeTab === "orders" || activeTab === "fulfillment") && (
          <div style={{ animation: "ordersFadeUp 0.3s ease" }}>
            {activeTab === "orders" && (
              <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1.25rem", alignItems: "center", flexWrap: "wrap" }}>
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by order ID, customer, city..." style={{ ...iStyle, width: 300, padding: "0.5rem 0.75rem" }} data-testid="orders-search" />
                <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ ...iStyle, width: 160 }} data-testid="orders-filter">
                  {["All", ...Object.keys(STATUS_META)].map(s => <option key={s}>{s}</option>)}
                </select>
              </div>
            )}

            <div style={{ border: `1px solid ${C.border}`, overflow: "auto" }}>
              {/* Table Header */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr 1.5fr 1fr 1fr 1fr 90px", padding: "0.58rem 1rem", background: C.bg, borderBottom: `1px solid ${C.border}`, minWidth: "900px" }}>
                {["Order ID", "Customer", "Date", "Total", "Status", "Payment", ""].map(h => (
                  <div key={h} style={{ fontSize: "0.54rem", letterSpacing: "0.2em", color: C.textMuted, textTransform: "uppercase", fontFamily: FM }}>{h}</div>
                ))}
              </div>

              {(activeTab === "fulfillment" ? fulfillmentOrders : filtered).map((o, i) => (
                <OrderRow key={o.id} order={o} idx={i} onSelect={setSelectedOrder} />
              ))}

              {(activeTab === "fulfillment" ? fulfillmentOrders : filtered).length === 0 && (
                <div style={{ padding: "2.5rem", textAlign: "center", color: C.textMuted, fontFamily: FM, fontSize: "0.72rem" }}>
                  {activeTab === "fulfillment" ? "✓ All orders fulfilled" : "No orders match your search"}
                </div>
              )}
            </div>

            <div style={{ padding: "0.65rem 1rem", fontSize: "0.6rem", color: C.textMuted, fontFamily: FM }}>
              {activeTab === "orders" ? `${filtered.length} of ${orders.length} orders` : `${fulfillmentOrders.length} orders need fulfillment`}
            </div>
          </div>
        )}
      </div>

      {/* Roadmap Footer */}
      <div style={{ borderTop: `1px solid ${C.border}`, padding: "0.8rem 2rem", display: "flex", gap: "1.5rem", background: C.surface, flexWrap: "wrap" }}>
        {[
          { label: "01 · Inventory", done: true },
          { label: "02 · CRM", done: true },
          { label: "03 · Orders", active: true },
          { label: "04 · Accounting", done: false },
        ].map(m => (
          <div key={m.label} style={{ fontSize: "0.56rem", letterSpacing: "0.15em", color: m.active ? C.gold : m.done ? C.greenBright : C.textMuted, fontFamily: FM, textTransform: "uppercase", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            {m.active && <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.gold, animation: "ordersPulse 2s infinite" }} />}
            {m.done && <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.greenBright }} />}
            {m.label}
          </div>
        ))}
      </div>

      {/* Modals */}
      {selectedOrder && (
        <OrderDetail order={selectedOrder} onClose={() => setSelectedOrder(null)}
          onUpdate={updated => { setOrders(prev => prev.map(o => o.id === updated.id ? updated : o)); }} />
      )}
      {showCreate && (
        <CreateOrderModal onClose={() => setShowCreate(false)} onAdd={handleAddOrder} />
      )}
    </div>
    </OrdersThemeContext.Provider>
  );
}
