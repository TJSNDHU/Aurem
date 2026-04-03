import { useState, useMemo } from "react";

// ─── THEME (ReRoots Brand Colors) ────────────────────────────
const C = {
  bg: "#FDF9F9",
  surface: "#FFFFFF",
  surfaceAlt: "#FEF6F7",
  border: "#F0E8E8",
  borderMid: "#E8D8DA",
  pink: "#F8A5B8",
  pinkDim: "#E8889A",
  pinkFaint: "rgba(248,165,184,0.08)",
  dark: "#2D2A2E",
  textDim: "#8A8490",
  textMuted: "#C4BAC0",
  green: "#72B08A",
  greenFaint: "rgba(114,176,138,0.08)",
  amber: "#E8A860",
  amberFaint: "rgba(232,168,96,0.08)",
  red: "#E07070",
  redFaint: "rgba(224,112,112,0.08)",
  blue: "#7AAEC8",
  blueFaint: "rgba(122,174,200,0.08)",
};

const FD = "'Cormorant Garamond', Georgia, serif";
const FS = "'Inter', system-ui, sans-serif";
const FM = "'JetBrains Mono', monospace";

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@300;400&display=swap');
  .hr-comp:hover { background: ${C.surfaceAlt} !important; cursor: pointer; }
  .hb-comp:hover { opacity: .8; transform: translateY(-1px); }
  .hc-comp:hover { border-color: ${C.pinkDim} !important; box-shadow: 0 2px 12px rgba(248,165,184,0.12); }
  .tab-b-comp:hover { color: ${C.pink} !important; }
  @keyframes fadeUpComp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  @keyframes pulseComp { 0%,100%{opacity:1;} 50%{opacity:.3;} }
`;

// ─── DATA ─────────────────────────────────────────────────────
const today = new Date();
const dA = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return d.toISOString().split("T")[0]; };
const dF = (n) => { const d = new Date(today); d.setDate(d.getDate() + n); return d.toISOString().split("T")[0]; };
const fDate = (s) => s ? new Date(s).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" }) : "—";
const daysUntil = (s) => s ? Math.ceil((new Date(s) - today) / 86400000) : null;

const INGREDIENTS = [
  { id: "C001", name: "PDRN Concentrate 2%", category: "Active", hcStatus: "Approved", hcNumber: "NPN-80094521", approvedDate: dA(180), expiryDate: dF(185), documents: ["NPN Certificate", "Safety Data Sheet", "CoA"], supplier: "BioLab Korea", riskLevel: "Low", notes: "Polynucleotide — verified for cosmetic use" },
  { id: "C002", name: "Hyaluronic Acid (HMW)", category: "Humectant", hcStatus: "Approved", hcNumber: "NPN-80041233", approvedDate: dA(365), expiryDate: dF(365), documents: ["NPN Certificate", "CoA", "MSDS"], supplier: "Bloomage Biotech", riskLevel: "Low", notes: "Standard cosmetic ingredient — no restrictions" },
  { id: "C003", name: "Niacinamide B3 USP", category: "Active", hcStatus: "Approved", hcNumber: "NPN-80029871", approvedDate: dA(200), expiryDate: dF(165), documents: ["NPN Certificate", "CoA"], supplier: "DSM Nutrition", riskLevel: "Low", notes: "Max 5% concentration for cosmetic use" },
  { id: "C004", name: "Ceramide NP", category: "Lipid", hcStatus: "Approved", hcNumber: "NPN-80058342", approvedDate: dA(90), expiryDate: dF(275), documents: ["NPN Certificate", "Safety Data Sheet"], supplier: "Evonik Industries", riskLevel: "Low", notes: "" },
  { id: "C005", name: "Peptide Complex GHK-Cu", category: "Peptide", hcStatus: "Pending", hcNumber: "", approvedDate: null, expiryDate: null, documents: ["Application Submitted", "Safety Dossier"], supplier: "Sino Peptide", riskLevel: "Medium", notes: "Application submitted Jan 15 2026 — awaiting HC review. Est. 90-day review." },
  { id: "C006", name: "Retinol 0.5% Solution", category: "Retinoid", hcStatus: "Approved", hcNumber: "NPN-80071209", approvedDate: dA(120), expiryDate: dF(15), documents: ["NPN Certificate", "CoA", "Stability Study"], supplier: "BASF SE", riskLevel: "High", notes: "Requires concentration declaration on label. Max 1% for OTC." },
  { id: "C007", name: "Sodium Hyaluronate (LMW)", category: "Humectant", hcStatus: "Approved", hcNumber: "NPN-80041290", approvedDate: dA(300), expiryDate: dF(65), documents: ["NPN Certificate", "CoA"], supplier: "Bloomage Biotech", riskLevel: "Low", notes: "" },
  { id: "C008", name: "Bakuchiol Extract 1%", category: "Active", hcStatus: "Under Review", hcNumber: "", approvedDate: null, expiryDate: null, documents: ["Initial Inquiry", "Safety Data"], supplier: "Indena S.p.A.", riskLevel: "Medium", notes: "Natural retinol alternative — HC review in progress since Dec 2025" },
  { id: "C009", name: "Azelaic Acid 10%", category: "Active", hcStatus: "Approved", hcNumber: "NPN-80062841", approvedDate: dA(150), expiryDate: dF(215), documents: ["NPN Certificate", "CoA", "Clinical Safety"], supplier: "Symrise AG", riskLevel: "Medium", notes: "DIN required if marketed for acne claims" },
];

const PRODUCTS = [
  { id: "P001", name: "PDRN Repair Serum 30ml", skuCode: "RR-SER-30", status: "Licensed", licenseNo: "CN-2025-4821", licensedDate: dA(90), renewalDate: dF(275), labelCompliant: true, claimsReviewed: true, ingredients: ["C001", "C002", "C003"], warnings: [] },
  { id: "P002", name: "PDRN Eye Recovery 15ml", skuCode: "RR-EYE-15", status: "Licensed", licenseNo: "CN-2025-4822", licensedDate: dA(85), renewalDate: dF(280), labelCompliant: true, claimsReviewed: true, ingredients: ["C001", "C002", "C004"], warnings: [] },
  { id: "P003", name: "Barrier Restore Cream 50ml", skuCode: "RR-CRM-50", status: "Licensed", licenseNo: "CN-2025-4823", licensedDate: dA(60), renewalDate: dF(305), labelCompliant: true, claimsReviewed: true, ingredients: ["C002", "C004", "C007"], warnings: [] },
  { id: "P004", name: "PDRN Ampoule 10x2ml", skuCode: "RR-AMP-10", status: "Licensed", licenseNo: "CN-2025-4824", licensedDate: dA(30), renewalDate: dF(335), labelCompliant: true, claimsReviewed: false, ingredients: ["C001", "C002"], warnings: ["Claims review pending"] },
  { id: "P005", name: "Peptide Firming Concentrate 30ml", skuCode: "RR-PEP-30", status: "Pending", licenseNo: "", licensedDate: null, renewalDate: null, labelCompliant: false, claimsReviewed: false, ingredients: ["C005", "C002", "C009"], warnings: ["Contains pending ingredient GHK-Cu", "Label not yet compliant", "Do not sell until licensed"] },
  { id: "P006", name: "Retinol Renewal Serum 30ml", skuCode: "RR-RET-30", status: "In Progress", licenseNo: "", licensedDate: null, renewalDate: null, labelCompliant: false, claimsReviewed: false, ingredients: ["C006", "C002", "C007"], warnings: ["Retinol concentration label required", "Claims review needed"] },
];

const TASKS_INIT = [
  { id: "T001", title: "Renew Retinol 0.5% NPN Certificate", priority: "High", dueDate: dF(15), status: "Open", linkedTo: "C006", type: "Renewal", assignee: "Tj" },
  { id: "T002", title: "Renew Sodium Hyaluronate NPN", priority: "Medium", dueDate: dF(65), status: "Open", linkedTo: "C007", type: "Renewal", assignee: "Tj" },
  { id: "T003", title: "Follow up with HC on GHK-Cu Pending Application", priority: "High", dueDate: dF(7), status: "Open", linkedTo: "C005", type: "Follow-Up", assignee: "Tj" },
  { id: "T004", title: "Complete claims review — PDRN Ampoule", priority: "Medium", dueDate: dF(14), status: "Open", linkedTo: "P004", type: "Compliance", assignee: "Tj" },
  { id: "T005", title: "Submit label update for Retinol Renewal Serum", priority: "High", dueDate: dF(21), status: "Open", linkedTo: "P006", type: "Label", assignee: "Tj" },
  { id: "T006", title: "Quarterly ingredient safety review", priority: "Low", dueDate: dF(45), status: "Open", linkedTo: null, type: "Review", assignee: "Tj" },
  { id: "T007", title: "Annual product listing renewal — HC Portal", priority: "Medium", dueDate: dF(90), status: "Open", linkedTo: null, type: "Renewal", assignee: "Tj" },
];

const STATUS_META = {
  Approved: { color: C.green, bg: C.greenFaint, icon: "✓" },
  Pending: { color: C.amber, bg: C.amberFaint, icon: "⧖" },
  "Under Review": { color: C.blue, bg: C.blueFaint, icon: "◎" },
  Expired: { color: C.red, bg: C.redFaint, icon: "✕" },
  Licensed: { color: C.green, bg: C.greenFaint, icon: "✓" },
  "In Progress": { color: C.amber, bg: C.amberFaint, icon: "⧖" },
  Open: { color: C.amber, bg: C.amberFaint },
  Done: { color: C.green, bg: C.greenFaint },
};

const PRIORITY_COLOR = { High: C.red, Medium: C.amber, Low: C.textDim };

// ─── SHARED UI ────────────────────────────────────────────────
const iStyle = { width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.dark, padding: "0.6rem 0.85rem", fontSize: "0.82rem", fontFamily: FS, borderRadius: 8, outline: "none" };
const bPri = { background: C.pink, color: "#fff", border: "none", padding: "0.6rem 1.4rem", fontSize: "0.75rem", letterSpacing: "0.05em", cursor: "pointer", fontFamily: FS, fontWeight: 500, borderRadius: 8, transition: "all 0.2s", whiteSpace: "nowrap" };
const bSec = { background: C.surface, color: C.pink, border: `1px solid ${C.pink}`, padding: "0.6rem 1.4rem", fontSize: "0.75rem", letterSpacing: "0.05em", cursor: "pointer", fontFamily: FS, fontWeight: 500, borderRadius: 8, transition: "all 0.2s", whiteSpace: "nowrap" };
const bGhost = { background: "transparent", color: C.textDim, border: "none", padding: "0.3rem 0.6rem", fontSize: "0.72rem", cursor: "pointer", fontFamily: FS };

function Badge({ label, color, bg, icon }) {
  return (
    <span style={{ fontSize: "0.65rem", letterSpacing: "0.05em", color, background: bg || `${color}15`, border: `1px solid ${color}30`, padding: "0.2rem 0.6rem", fontFamily: FS, fontWeight: 500, borderRadius: 20, whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
      {icon && <span>{icon}</span>}{label}
    </span>
  );
}

function KPI({ label, value, sub, color, pulse: p, i }) {
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.1rem 1.3rem", animation: `fadeUpComp 0.3s ${(i || 0) * 0.05}s both`, boxShadow: "0 1px 8px rgba(248,165,184,0.06)" }}>
      <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 500, marginBottom: "0.4rem" }}>{label}</div>
      <div style={{ fontSize: "1.7rem", color: color || C.pink, fontFamily: FD, fontWeight: 300, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FS, marginTop: "0.3rem" }}>{sub}</div>}
      {p && <div style={{ width: 5, height: 5, borderRadius: "50%", background: color, marginTop: "0.4rem", animation: "pulseComp 1.5s infinite", boxShadow: `0 0 6px ${color}` }} />}
    </div>
  );
}

function Modal({ title, children, onClose, wide }) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(45,42,46,0.5)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: C.surface, borderRadius: 16, border: `1px solid ${C.border}`, width: wide ? "min(780px,96vw)" : "min(560px,96vw)", maxHeight: "90vh", overflowY: "auto", animation: "fadeUpComp 0.2s ease", boxShadow: "0 20px 60px rgba(248,165,184,0.15)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1.1rem 1.5rem", borderBottom: `1px solid ${C.border}` }}>
          <span style={{ fontFamily: FD, fontSize: "1.15rem", color: C.dark, fontWeight: 500 }}>{title}</span>
          <button onClick={onClose} style={{ ...bGhost, fontSize: "1.3rem" }}>×</button>
        </div>
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
}

function FF({ label, children }) {
  return (
    <div style={{ marginBottom: "0.9rem" }}>
      <label style={{ display: "block", fontSize: "0.68rem", fontWeight: 500, color: C.textDim, fontFamily: FS, marginBottom: "0.3rem" }}>{label}</label>
      {children}
    </div>
  );
}

function AlertBanner({ items }) {
  if (!items.length) return null;
  return (
    <div style={{ background: `${C.red}10`, border: `1px solid ${C.red}30`, borderRadius: 10, padding: "0.85rem 1.1rem", marginBottom: "1.5rem", display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
      <span style={{ fontSize: "1rem", marginTop: "0.1rem" }}>⚠️</span>
      <div>
        <div style={{ fontSize: "0.75rem", fontWeight: 600, color: C.red, fontFamily: FS, marginBottom: "0.3rem" }}>Action Required</div>
        {items.map((item, i) => (
          <div key={i} style={{ fontSize: "0.72rem", color: C.dark, fontFamily: FS, lineHeight: 1.6 }}>· {item}</div>
        ))}
      </div>
    </div>
  );
}

// ─── OVERVIEW TAB ─────────────────────────────────────────────
function OverviewTab({ ingredients, products, tasks, onSelectIngredient, onSelectProduct }) {
  const approved = ingredients.filter(i => i.hcStatus === "Approved").length;
  const pending = ingredients.filter(i => i.hcStatus === "Pending" || i.hcStatus === "Under Review").length;
  const expiringSoon = ingredients.filter(i => {
    if (!i.expiryDate) return false;
    const d = daysUntil(i.expiryDate);
    return d !== null && d <= 30 && d > 0;
  });
  const overdueTasks = tasks.filter(t => t.status === "Open" && daysUntil(t.dueDate) <= 7);
  const readySell = products.filter(p => p.status === "Licensed" && p.labelCompliant && p.claimsReviewed).length;
  const blocked = products.filter(p => p.status !== "Licensed" || !p.labelCompliant).length;

  const alerts = [
    ...expiringSoon.map(i => `${i.name} NPN expires in ${daysUntil(i.expiryDate)} days`),
    ...overdueTasks.map(t => `${t.title} — due ${fDate(t.dueDate)}`),
    ...products.filter(p => p.warnings.length > 0 && p.status !== "Licensed").map(p => `${p.name}: ${p.warnings[0]}`),
  ];

  return (
    <div style={{ animation: "fadeUpComp 0.3s ease" }}>
      <AlertBanner items={alerts} />

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "0.75rem", marginBottom: "2rem" }}>
        <KPI i={0} label="HC Approved" value={approved} sub={`of ${ingredients.length} ingredients`} color={C.green} />
        <KPI i={1} label="Pending / Review" value={pending} sub="awaiting HC decision" color={C.amber} pulse={pending > 0} />
        <KPI i={2} label="Expiring (30d)" value={expiringSoon.length} sub="need renewal action" color={expiringSoon.length > 0 ? C.red : C.green} pulse={expiringSoon.length > 0} />
        <KPI i={3} label="Products Ready to Sell" value={`${readySell}/${products.length}`} sub={`${blocked} blocked`} color={C.pink} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        {/* Urgent Tasks */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.65rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 500, marginBottom: "1rem" }}>Urgent Compliance Tasks</div>
          {tasks.filter(t => t.status === "Open").sort((a, b) => new Date(a.dueDate) - new Date(b.dueDate)).slice(0, 5).map((task, i) => {
            const days = daysUntil(task.dueDate);
            const urgentColor = days <= 7 ? C.red : days <= 30 ? C.amber : C.textDim;
            return (
              <div key={task.id} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.65rem 0", borderBottom: i < 4 ? `1px solid ${C.border}` : "none", animation: `fadeUpComp 0.3s ${i * 0.05}s both` }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: PRIORITY_COLOR[task.priority], flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.78rem", color: C.dark, fontFamily: FS, fontWeight: 400 }}>{task.title}</div>
                  <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FS, marginTop: "0.15rem" }}>{task.type}</div>
                </div>
                <div style={{ fontSize: "0.65rem", color: urgentColor, fontFamily: FM, whiteSpace: "nowrap" }}>
                  {days <= 0 ? "Overdue" : `${days}d`}
                </div>
              </div>
            );
          })}
        </div>

        {/* Product Compliance Status */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem" }}>
          <div style={{ fontSize: "0.65rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 500, marginBottom: "1rem" }}>Product Sell Readiness</div>
          {products.map((p, i) => {
            const ready = p.status === "Licensed" && p.labelCompliant && p.claimsReviewed;
            const sm = STATUS_META[p.status] || STATUS_META["In Progress"];
            return (
              <div key={p.id} className="hr-comp" onClick={() => onSelectProduct(p)}
                style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.65rem 0.5rem", borderRadius: 8, borderBottom: i < products.length - 1 ? `1px solid ${C.border}` : "none", transition: "background 0.15s", animation: `fadeUpComp 0.3s ${i * 0.04}s both` }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: ready ? C.green : p.status === "Pending" ? C.red : C.amber, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "0.78rem", color: C.dark, fontFamily: FS }}>{p.name}</div>
                  {p.warnings.length > 0 && <div style={{ fontSize: "0.6rem", color: C.red, fontFamily: FS, marginTop: "0.1rem" }}>{p.warnings[0]}</div>}
                </div>
                <Badge label={p.status} color={sm.color} bg={sm.bg} icon={sm.icon} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── INGREDIENTS TAB ──────────────────────────────────────────
function IngredientsTab({ ingredients, onSelect, onAdd }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("All");

  const filtered = useMemo(() => ingredients.filter(i => {
    const ms = i.name.toLowerCase().includes(search.toLowerCase()) || i.category.toLowerCase().includes(search.toLowerCase());
    const mf = filter === "All" || i.hcStatus === filter;
    return ms && mf;
  }), [ingredients, search, filter]);

  return (
    <div style={{ animation: "fadeUpComp 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.25rem" }}>
        <div style={{ display: "flex", gap: "0.75rem" }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search ingredients..." style={{ ...iStyle, width: 240, padding: "0.5rem 0.85rem" }} />
          <select value={filter} onChange={e => setFilter(e.target.value)} style={{ ...iStyle, width: 160 }}>
            {["All", "Approved", "Pending", "Under Review", "Expired"].map(s => <option key={s}>{s}</option>)}
          </select>
        </div>
        <button style={bPri} className="hb-comp" onClick={onAdd}>+ Add Ingredient</button>
      </div>

      <div style={{ border: `1px solid ${C.border}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2.5fr 1fr 1.2fr 1.2fr 1fr 1fr 80px", padding: "0.65rem 1rem", background: C.surfaceAlt, borderBottom: `1px solid ${C.border}` }}>
          {["Ingredient", "Category", "HC Status", "NPN / Number", "Expiry", "Risk", ""].map(h => (
            <div key={h} style={{ fontSize: "0.6rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, fontWeight: 500 }}>{h}</div>
          ))}
        </div>

        {filtered.map((ing, i) => {
          const sm = STATUS_META[ing.hcStatus] || STATUS_META.Pending;
          const days = daysUntil(ing.expiryDate);
          const expiryColor = days !== null ? (days <= 0 ? C.red : days <= 30 ? C.red : days <= 90 ? C.amber : C.green) : C.textMuted;

          return (
            <div key={ing.id} className="hr-comp" onClick={() => onSelect(ing)}
              style={{ display: "grid", gridTemplateColumns: "2.5fr 1fr 1.2fr 1.2fr 1fr 1fr 80px", padding: "0.82rem 1rem", borderBottom: `1px solid ${C.border}`, background: i % 2 === 0 ? C.surface : C.bg, transition: "background 0.15s", animation: `fadeUpComp 0.3s ${i * 0.03}s both` }}>
              <div>
                <div style={{ fontSize: "0.85rem", color: C.dark, fontFamily: FS, fontWeight: 400 }}>{ing.name}</div>
                <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FS, marginTop: "0.1rem" }}>{ing.supplier}</div>
              </div>
              <div style={{ fontSize: "0.72rem", color: C.textDim, fontFamily: FS, alignSelf: "center" }}>{ing.category}</div>
              <div style={{ alignSelf: "center" }}><Badge label={ing.hcStatus} color={sm.color} bg={sm.bg} icon={sm.icon} /></div>
              <div style={{ fontSize: "0.72rem", color: ing.hcNumber ? C.blue : C.textMuted, fontFamily: FM, alignSelf: "center" }}>{ing.hcNumber || "—"}</div>
              <div style={{ alignSelf: "center" }}>
                <div style={{ fontSize: "0.72rem", color: expiryColor, fontFamily: FS }}>
                  {ing.expiryDate ? fDate(ing.expiryDate) : "—"}
                </div>
                {days !== null && days <= 90 && (
                  <div style={{ fontSize: "0.58rem", color: expiryColor, fontFamily: FM, marginTop: "0.1rem" }}>
                    {days <= 0 ? "Expired" : `${days}d left`}
                  </div>
                )}
              </div>
              <div style={{ alignSelf: "center" }}>
                <Badge label={ing.riskLevel} color={ing.riskLevel === "High" ? C.red : ing.riskLevel === "Medium" ? C.amber : C.green} />
              </div>
              <div style={{ alignSelf: "center" }}>
                <button style={bGhost} className="hb-comp">View →</button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PRODUCTS TAB ─────────────────────────────────────────────
function ProductsTab({ products, ingredients, onSelect }) {
  return (
    <div style={{ animation: "fadeUpComp 0.3s ease" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px,1fr))", gap: "1rem" }}>
        {products.map((p, i) => {
          const sm = STATUS_META[p.status] || STATUS_META["In Progress"];
          const pIngredients = ingredients.filter(ing => p.ingredients.includes(ing.id));
          const hasIssues = pIngredients.some(ing => ing.hcStatus !== "Approved");
          const renewalDays = daysUntil(p.renewalDate);

          return (
            <div key={p.id} className="hc-comp" onClick={() => onSelect(p)}
              style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem", cursor: "pointer", transition: "all 0.2s", animation: `fadeUpComp 0.4s ${i * 0.06}s both`, boxShadow: "0 1px 8px rgba(248,165,184,0.05)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
                <div>
                  <div style={{ fontFamily: FD, fontSize: "1.05rem", color: C.dark, fontWeight: 500, lineHeight: 1.3 }}>{p.name}</div>
                  <div style={{ fontSize: "0.65rem", color: C.textDim, fontFamily: FM, marginTop: "0.25rem" }}>{p.skuCode}</div>
                </div>
                <Badge label={p.status} color={sm.color} bg={sm.bg} icon={sm.icon} />
              </div>

              {/* Compliance checklist */}
              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginBottom: "1rem" }}>
                {[
                  ["HC License", p.status === "Licensed"],
                  ["Label Compliant", p.labelCompliant],
                  ["Claims Reviewed", p.claimsReviewed],
                  ["Ingredients Approved", !hasIssues],
                ].map(([label, ok]) => (
                  <div key={label} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <span style={{ width: 16, height: 16, borderRadius: "50%", background: ok ? C.greenFaint : C.redFaint, border: `1px solid ${ok ? C.green : C.red}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.6rem", color: ok ? C.green : C.red, flexShrink: 0 }}>
                      {ok ? "✓" : "✕"}
                    </span>
                    <span style={{ fontSize: "0.72rem", color: ok ? C.dark : C.red, fontFamily: FS }}>{label}</span>
                  </div>
                ))}
              </div>

              {p.warnings.length > 0 && (
                <div style={{ background: C.redFaint, borderRadius: 8, padding: "0.6rem 0.75rem", marginBottom: "0.75rem" }}>
                  {p.warnings.map((w, j) => (
                    <div key={j} style={{ fontSize: "0.65rem", color: C.red, fontFamily: FS, lineHeight: 1.6 }}>⚠ {w}</div>
                  ))}
                </div>
              )}

              {p.licenseNo && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: C.textDim, fontFamily: FM, paddingTop: "0.75rem", borderTop: `1px solid ${C.border}` }}>
                  <span>{p.licenseNo}</span>
                  {renewalDays !== null && (
                    <span style={{ color: renewalDays <= 90 ? C.amber : C.textDim }}>
                      Renewal in {renewalDays}d
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── TASKS TAB ────────────────────────────────────────────────
function TasksTab({ tasks, setTasks }) {
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({});
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const toggleDone = (id) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, status: t.status === "Done" ? "Open" : "Done" } : t));
  };

  const handleAdd = () => {
    if (!form.title || !form.dueDate) return;
    setTasks(prev => [...prev, {
      id: `T${String(Date.now()).slice(-4)}`,
      title: form.title, priority: form.priority || "Medium",
      dueDate: form.dueDate, status: "Open",
      linkedTo: null, type: form.type || "Compliance", assignee: "Tj"
    }]);
    setShowAdd(false); setForm({});
  };

  const open = tasks.filter(t => t.status === "Open").sort((a, b) => new Date(a.dueDate) - new Date(b.dueDate));
  const done = tasks.filter(t => t.status === "Done");

  return (
    <div style={{ animation: "fadeUpComp 0.3s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
        <div style={{ fontFamily: FD, fontSize: "1.2rem", color: C.dark, fontWeight: 400 }}>
          Compliance Tasks <span style={{ fontSize: "0.9rem", color: C.textDim }}>({open.length} open)</span>
        </div>
        <button style={bPri} className="hb-comp" onClick={() => setShowAdd(true)}>+ Add Task</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "2rem" }}>
        {open.map((task, i) => {
          const days = daysUntil(task.dueDate);
          const urgentColor = days <= 0 ? C.red : days <= 7 ? C.red : days <= 30 ? C.amber : C.textDim;

          return (
            <div key={task.id} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "0.85rem 1rem", background: C.surface, border: `1px solid ${C.border}`, borderLeft: `3px solid ${PRIORITY_COLOR[task.priority]}`, borderRadius: "0 8px 8px 0", animation: `fadeUpComp 0.3s ${i * 0.04}s both` }}>
              <input type="checkbox" checked={task.status === "Done"} onChange={() => toggleDone(task.id)}
                style={{ width: 16, height: 16, accentColor: C.pink, cursor: "pointer", flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: "0.82rem", color: C.dark, fontFamily: FS, fontWeight: 400 }}>{task.title}</div>
                <div style={{ fontSize: "0.62rem", color: C.textDim, fontFamily: FS, marginTop: "0.15rem" }}>{task.type}</div>
              </div>
              <Badge label={task.priority} color={PRIORITY_COLOR[task.priority]} />
              <div style={{ textAlign: "right", minWidth: 80 }}>
                <div style={{ fontSize: "0.7rem", color: urgentColor, fontFamily: FM, fontWeight: 400 }}>
                  {days <= 0 ? "Overdue" : `${days} days`}
                </div>
                <div style={{ fontSize: "0.6rem", color: C.textMuted, fontFamily: FS }}>{fDate(task.dueDate)}</div>
              </div>
            </div>
          );
        })}
      </div>

      {done.length > 0 && (
        <div>
          <div style={{ fontSize: "0.62rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS, marginBottom: "0.75rem" }}>Completed ({done.length})</div>
          {done.map((task) => (
            <div key={task.id} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "0.65rem 1rem", marginBottom: "0.4rem", background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, opacity: 0.6 }}>
              <input type="checkbox" checked onChange={() => toggleDone(task.id)} style={{ width: 16, height: 16, accentColor: C.green, cursor: "pointer" }} />
              <div style={{ flex: 1, fontSize: "0.78rem", color: C.textDim, fontFamily: FS, textDecoration: "line-through" }}>{task.title}</div>
              <Badge label="Done" color={C.green} />
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <Modal title="Add Compliance Task" onClose={() => setShowAdd(false)}>
          <FF label="Task Title *"><input style={iStyle} value={form.title || ""} onChange={e => set("title", e.target.value)} placeholder="e.g. Renew NPN Certificate for..." /></FF>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 1rem" }}>
            <FF label="Type">
              <select style={iStyle} value={form.type || "Compliance"} onChange={e => set("type", e.target.value)}>
                {["Compliance", "Renewal", "Follow-Up", "Label", "Review", "Submission"].map(t => <option key={t}>{t}</option>)}
              </select>
            </FF>
            <FF label="Priority">
              <select style={iStyle} value={form.priority || "Medium"} onChange={e => set("priority", e.target.value)}>
                {["High", "Medium", "Low"].map(p => <option key={p}>{p}</option>)}
              </select>
            </FF>
          </div>
          <FF label="Due Date *"><input style={iStyle} type="date" value={form.dueDate || ""} onChange={e => set("dueDate", e.target.value)} /></FF>
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "0.5rem" }}>
            <button style={bSec} onClick={() => setShowAdd(false)}>Cancel</button>
            <button style={bPri} className="hb-comp" onClick={handleAdd}>Add Task</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── INGREDIENT DETAIL MODAL ──────────────────────────────────
function IngredientDetail({ ingredient: ing, onClose }) {
  const sm = STATUS_META[ing.hcStatus] || STATUS_META.Pending;
  const days = daysUntil(ing.expiryDate);
  const expiryColor = days !== null ? (days <= 0 ? C.red : days <= 30 ? C.red : days <= 90 ? C.amber : C.green) : C.textMuted;

  return (
    <Modal title={ing.name} onClose={onClose} wide>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        <div style={{ background: C.bg, borderRadius: 10, padding: "1rem", border: `1px solid ${C.border}` }}>
          {[
            ["HC Status", <Badge key="status" label={ing.hcStatus} color={sm.color} bg={sm.bg} icon={sm.icon} />],
            ["NPN Number", ing.hcNumber || "Not yet assigned"],
            ["Category", ing.category],
            ["Supplier", ing.supplier],
            ["Risk Level", ing.riskLevel],
          ].map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: `1px solid ${C.border}` }}>
              <span style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FS }}>{k}</span>
              <span style={{ fontSize: "0.75rem", color: C.dark, fontFamily: FS }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ background: C.bg, borderRadius: 10, padding: "1rem", border: `1px solid ${C.border}` }}>
          {[
            ["Approved Date", fDate(ing.approvedDate)],
            ["Expiry Date", ing.expiryDate ? fDate(ing.expiryDate) : "—"],
            ["Days Remaining", days !== null ? (days <= 0 ? "EXPIRED" : `${days} days`) : "—"],
          ].map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: `1px solid ${C.border}` }}>
              <span style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: FS }}>{k}</span>
              <span style={{ fontSize: "0.75rem", color: k === "Days Remaining" ? expiryColor : C.dark, fontFamily: FS, fontWeight: k === "Days Remaining" ? 500 : 400 }}>{v}</span>
            </div>
          ))}

          <div style={{ marginTop: "0.75rem" }}>
            <div style={{ fontSize: "0.62rem", color: C.textMuted, fontFamily: FS, marginBottom: "0.4rem" }}>DOCUMENTS ON FILE</div>
            {ing.documents.map((doc, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.3rem 0" }}>
                <span style={{ color: C.green, fontSize: "0.7rem" }}>✓</span>
                <span style={{ fontSize: "0.72rem", color: C.dark, fontFamily: FS }}>{doc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {ing.notes && (
        <div style={{ background: C.pinkFaint, border: `1px solid ${C.pink}30`, borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "1rem", fontSize: "0.78rem", color: C.dark, fontFamily: FS, lineHeight: 1.7 }}>
          {ing.notes}
        </div>
      )}

      <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
        <button style={bSec} onClick={onClose}>Close</button>
        <button style={bPri} className="hb-comp">Upload Document</button>
        {ing.hcStatus === "Approved" && days !== null && days <= 90 && (
          <button style={{ ...bPri, background: C.amber }} className="hb-comp">Initiate Renewal</button>
        )}
      </div>
    </Modal>
  );
}

// ─── MAIN ─────────────────────────────────────────────────────
export default function HealthCanadaCompliance() {
  const [activeTab, setActiveTab] = useState("overview");
  const [ingredients] = useState(INGREDIENTS);
  const [products] = useState(PRODUCTS);
  const [tasks, setTasks] = useState(TASKS_INIT);
  const [selectedIngredient, setSelectedIngredient] = useState(null);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [showAddIngredient, setShowAddIngredient] = useState(false);

  const urgentCount = tasks.filter(t => t.status === "Open" && daysUntil(t.dueDate) <= 30).length;

  const tabs = [
    { id: "overview", label: "Overview", icon: "◈" },
    { id: "ingredients", label: `Ingredients (${ingredients.length})`, icon: "⚗" },
    { id: "products", label: `Products (${products.length})`, icon: "◎" },
    { id: "tasks", label: `Tasks (${tasks.filter(t => t.status === "Open").length})`, icon: "◉", alert: urgentCount > 0 },
  ];

  return (
    <div style={{ minHeight: "100%", fontFamily: FS, color: C.dark }} data-testid="hc-compliance-module">
      <style>{css}</style>

      {/* Header */}
      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "1.1rem 1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: "1rem" }}>
          <span style={{ fontFamily: FD, fontSize: "1.3rem", color: C.dark, fontWeight: 400 }}>
            Health Canada Compliance
          </span>
          <span style={{ fontSize: "0.62rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: FS }}>Regulatory Tracker</span>
        </div>
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.68rem", color: C.green, fontFamily: FS }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green }} />
            Reroots Aesthetics Inc.
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "0 1.5rem", display: "flex" }}>
        {tabs.map(t => (
          <button key={t.id} className="tab-b-comp" onClick={() => setActiveTab(t.id)}
            style={{ background: "none", border: "none", borderBottom: `2px solid ${activeTab === t.id ? C.pink : "transparent"}`, padding: "0.85rem 1.1rem", cursor: "pointer", color: activeTab === t.id ? C.pink : C.textDim, fontSize: "0.78rem", fontFamily: FS, fontWeight: activeTab === t.id ? 500 : 400, transition: "all 0.2s", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            {t.icon} {t.label}
            {t.alert && <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.red, animation: "pulseComp 1.5s infinite" }} />}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: "1.5rem" }}>
        {activeTab === "overview" && <OverviewTab ingredients={ingredients} products={products} tasks={tasks} onSelectIngredient={setSelectedIngredient} onSelectProduct={setSelectedProduct} />}
        {activeTab === "ingredients" && <IngredientsTab ingredients={ingredients} onSelect={setSelectedIngredient} onAdd={() => setShowAddIngredient(true)} />}
        {activeTab === "products" && <ProductsTab products={products} ingredients={ingredients} onSelect={setSelectedProduct} />}
        {activeTab === "tasks" && <TasksTab tasks={tasks} setTasks={setTasks} />}
      </div>

      {/* Modals */}
      {selectedIngredient && <IngredientDetail ingredient={selectedIngredient} onClose={() => setSelectedIngredient(null)} />}
    </div>
  );
}
