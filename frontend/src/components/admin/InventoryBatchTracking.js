import { useState, useEffect, createContext, useContext } from "react";
import axios from "axios";
import { useAdminBrand } from "./useAdminBrand";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Theme context for passing to sub-components
const InvThemeContext = createContext(null);
const useInvTheme = () => useContext(InvThemeContext);

// ─── INITIAL DATA ─────────────────────────────────────────────────────────────
const INITIAL_INGREDIENTS = [
  { id: "ING-001", name: "PDRN Concentrate 2%", supplier: "BioLab Korea", unit: "ml", stock: 4500, reorderPoint: 1000, cost: 0.85, category: "Active", healthCanada: "Approved", lastUpdated: "2026-02-28" },
  { id: "ING-002", name: "Hyaluronic Acid (HMW)", supplier: "Bloomage Biotech", unit: "g", stock: 2200, reorderPoint: 500, cost: 0.12, category: "Humectant", healthCanada: "Approved", lastUpdated: "2026-02-25" },
  { id: "ING-003", name: "Niacinamide B3 USP", supplier: "DSM Nutrition", unit: "g", stock: 3800, reorderPoint: 800, cost: 0.04, category: "Active", healthCanada: "Approved", lastUpdated: "2026-02-20" },
  { id: "ING-004", name: "Ceramide NP", supplier: "Evonik Industries", unit: "g", stock: 380, reorderPoint: 400, cost: 1.20, category: "Lipid", healthCanada: "Approved", lastUpdated: "2026-02-18" },
  { id: "ING-005", name: "Peptide Complex GHK-Cu", supplier: "Sino Peptide", unit: "g", stock: 150, reorderPoint: 100, cost: 4.50, category: "Peptide", healthCanada: "Pending", lastUpdated: "2026-02-15" },
  { id: "ING-006", name: "Sodium Hyaluronate (LMW)", supplier: "Bloomage Biotech", unit: "g", stock: 1900, reorderPoint: 400, cost: 0.18, category: "Humectant", healthCanada: "Approved", lastUpdated: "2026-02-28" },
  { id: "ING-007", name: "Retinol 0.5% Solution", supplier: "BASF SE", unit: "ml", stock: 820, reorderPoint: 300, cost: 0.65, category: "Retinoid", healthCanada: "Approved", lastUpdated: "2026-02-22" },
];

// La Vela Bianca specific ingredients
const LAVELA_INGREDIENTS = [
  { id: "ING-L01", name: "Centella Asiatica Extract", supplier: "Jeju BioLab", unit: "ml", stock: 3200, reorderPoint: 800, cost: 0.45, category: "Active", healthCanada: "Approved", lastUpdated: "2026-03-01" },
  { id: "ING-L02", name: "Niacinamide 5% Solution", supplier: "DSM Nutrition", unit: "g", stock: 2800, reorderPoint: 600, cost: 0.03, category: "Active", healthCanada: "Approved", lastUpdated: "2026-03-01" },
  { id: "ING-L03", name: "Aloe Vera Gel 200x", supplier: "Terry Labs", unit: "g", stock: 1500, reorderPoint: 400, cost: 0.08, category: "Soothing", healthCanada: "Approved", lastUpdated: "2026-03-01" },
  { id: "ING-L04", name: "Panthenol (Vitamin B5)", supplier: "BASF SE", unit: "g", stock: 1200, reorderPoint: 300, cost: 0.15, category: "Hydration", healthCanada: "Approved", lastUpdated: "2026-03-01" },
];

const INITIAL_PRODUCTS = [
  { id: "SKU-001", name: "PDRN Repair Serum 30ml", batch: "RR-2026-001", manufactured: "2026-01-15", expiry: "2028-01-15", stock: 284, allocated: 45, status: "Active", formula: "F-001" },
  { id: "SKU-002", name: "PDRN Eye Recovery 15ml", batch: "RR-2026-002", manufactured: "2026-01-20", expiry: "2028-01-20", stock: 156, allocated: 22, status: "Active", formula: "F-002" },
  { id: "SKU-003", name: "Barrier Restore Cream 50ml", batch: "RR-2026-003", manufactured: "2026-02-01", expiry: "2028-02-01", stock: 92, allocated: 18, status: "Active", formula: "F-003" },
  { id: "SKU-004", name: "PDRN Ampoule 10x2ml", batch: "RR-2026-004", manufactured: "2026-02-10", expiry: "2027-08-10", stock: 48, allocated: 12, status: "Low Stock", formula: "F-004" },
  { id: "SKU-005", name: "Peptide Firming Concentrate 30ml", batch: "RR-2026-005", manufactured: "2026-02-15", expiry: "2028-02-15", stock: 0, allocated: 0, status: "Out of Stock", formula: "F-005" },
];

// La Vela products
const LAVELA_PRODUCTS = [
  { id: "SKU-LV01", name: "ORO ROSA Serum 30ml", batch: "LV-2026-001", manufactured: "2026-03-01", expiry: "2028-03-01", stock: 500, allocated: 0, status: "Active", formula: "LV-001" },
];

const INITIAL_BATCHES = [
  { id: "BATCH-001", product: "PDRN Repair Serum 30ml", batchNo: "RR-2026-001", qty: 500, qcStatus: "Passed", manufactured: "2026-01-15", expiry: "2028-01-15", notes: "Nominal PDRN concentration verified at 2.1%" },
  { id: "BATCH-002", product: "PDRN Eye Recovery 15ml", batchNo: "RR-2026-002", qty: 300, qcStatus: "Passed", manufactured: "2026-01-20", expiry: "2028-01-20", notes: "pH 6.2 — within spec" },
  { id: "BATCH-003", product: "Barrier Restore Cream 50ml", batchNo: "RR-2026-003", qty: 200, qcStatus: "Passed", manufactured: "2026-02-01", expiry: "2028-02-01", notes: "Ceramide dispersion confirmed" },
  { id: "BATCH-004", product: "PDRN Ampoule 10x2ml", batchNo: "RR-2026-004", qty: 100, qcStatus: "Passed", manufactured: "2026-02-10", expiry: "2027-08-10", notes: "Shorter expiry — single use ampoule format" },
  { id: "BATCH-005", product: "Peptide Firming Concentrate", batchNo: "RR-2026-005", qty: 150, qcStatus: "In Review", manufactured: "2026-02-15", expiry: "2028-02-15", notes: "Awaiting GHK-Cu stability results" },
];

const LAVELA_BATCHES = [
  { id: "BATCH-LV01", product: "ORO ROSA Serum 30ml", batchNo: "LV-2026-001", qty: 500, qcStatus: "Passed", manufactured: "2026-03-01", expiry: "2028-03-01", notes: "Centella extract concentration verified. pH 5.2 — teen-safe" },
];

// ─── BRAND THEME (Dynamic) ───────────────────────────────────────────────────────
const getThemeColors = (isLaVela) => isLaVela ? {
  bg: "#0D4D4D", surface: "#1A6B6B", surfaceHover: "#1A6B6B80",
  border: "#D4A57440", borderLight: "#D4A57430",
  gold: "#D4A574", goldDim: "#E6BE8A",
  green: "#72B08A", greenBright: "#72B08A",
  red: "#E07070", redBright: "#E07070",
  amber: "#E8A860",
  text: "#FDF8F5", textDim: "#D4A574", textMuted: "#E8C4B8",
  white: "#FDF8F5",
} : {
  bg: "#FDF9F9", surface: "#FFFFFF", surfaceHover: "#FEF2F4",
  border: "#F0E8E8", borderLight: "#E8DEE0",
  gold: "#F8A5B8", goldDim: "#E8889A",
  green: "#72B08A", greenBright: "#72B08A",
  red: "#E07070", redBright: "#E07070",
  amber: "#E8A860",
  text: "#2D2A2E", textDim: "#8A8490", textMuted: "#C4BAC0",
  white: "#2D2A2E",
};

// Generate CSS dynamically based on theme colors
const generateCss = (C) => `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=JetBrains+Mono:wght@300;400&display=swap');
  .inv-module * { box-sizing: border-box; margin: 0; padding: 0; }
  .inv-module ::-webkit-scrollbar { width: 3px; height: 3px; }
  .inv-module ::-webkit-scrollbar-track { background: ${C.bg}; }
  .inv-module ::-webkit-scrollbar-thumb { background: ${C.borderLight}; border-radius: 2px; }
  @keyframes invFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes invPulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
  @keyframes invSlideIn { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:translateX(0); } }
  .inv-row-hover:hover { background: ${C.surfaceHover} !important; transition: background 0.15s; }
  .inv-btn-hover:hover { opacity: 0.75; transform: translateY(-1px); }
  .inv-tab-item:hover { color: ${C.gold} !important; }
  .inv-module input:focus, .inv-module textarea:focus, .inv-module select:focus { outline: none; border-color: ${C.goldDim} !important; }
`;

// Dynamic style getters
const getInputStyle = (C) => ({ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text, padding: "0.6rem 0.75rem", fontSize: "0.82rem", fontFamily: "JetBrains Mono" });
const getBtnPrimary = (C) => ({ background: C.gold, color: C.bg, border: "none", padding: "0.65rem 1.5rem", fontSize: "0.68rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: "JetBrains Mono", transition: "all 0.2s" });
const getBtnSecondary = (C) => ({ background: "transparent", color: C.textDim, border: `1px solid ${C.border}`, padding: "0.65rem 1.5rem", fontSize: "0.68rem", letterSpacing: "0.2em", textTransform: "uppercase", cursor: "pointer", fontFamily: "JetBrains Mono", transition: "all 0.2s" });

// ─── HELPERS ─────────────────────────────────────────────────────────────────
const pct = (v, total) => Math.min(100, Math.round((v / total) * 100));
const fmtDate = (d) => new Date(d).toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" });
const getStockStatus = (C) => (stock, reorder) => {
  if (stock === 0) return { label: "OUT", color: C.redBright };
  if (stock <= reorder) return { label: "LOW", color: C.amber };
  return { label: "OK", color: C.greenBright };
};

// ─── SUB-COMPONENTS ───────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent, pulse: doPulse }) {
  const C = useInvTheme();
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: "1.25rem 1.5rem", animation: "invFadeIn 0.4s ease both" }}>
      <div style={{ fontSize: "0.6rem", letterSpacing: "0.3em", color: C.textMuted, textTransform: "uppercase", marginBottom: "0.5rem", fontFamily: "JetBrains Mono" }}>{label}</div>
      <div style={{ fontSize: "1.8rem", color: accent || C.gold, fontFamily: "Cormorant Garamond", fontWeight: 300, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: "0.68rem", color: C.textDim, marginTop: "0.4rem", fontFamily: "JetBrains Mono" }}>{sub}</div>}
      {doPulse && <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.redBright, marginTop: "0.5rem", animation: "invPulse 1.5s infinite", boxShadow: `0 0 8px ${C.redBright}` }} />}
    </div>
  );
}

function Badge({ label, color }) {
  return (
    <span style={{ fontSize: "0.58rem", letterSpacing: "0.15em", color, border: `1px solid ${color}`, padding: "0.15rem 0.5rem", fontFamily: "JetBrains Mono", opacity: 0.9 }}>
      {label}
    </span>
  );
}

function Modal({ title, children, onClose }) {
  const C = useInvTheme();
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{ background: C.surface, border: `1px solid ${C.borderLight}`, width: "min(560px, 95vw)", maxHeight: "85vh", overflowY: "auto", animation: "invFadeIn 0.2s ease" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "1.25rem 1.5rem", borderBottom: `1px solid ${C.border}` }}>
          <span style={{ fontFamily: "Cormorant Garamond", fontSize: "1.1rem", color: C.white, fontWeight: 400 }}>{title}</span>
          <button onClick={onClose} style={{ background: "none", border: "none", color: C.textDim, cursor: "pointer", fontSize: "1.2rem", lineHeight: 1 }}>×</button>
        </div>
        <div style={{ padding: "1.5rem" }}>{children}</div>
      </div>
    </div>
  );
}

function FormField({ label, children }) {
  const C = useInvTheme();
  return (
    <div style={{ marginBottom: "1rem" }}>
      <label style={{ display: "block", fontSize: "0.62rem", letterSpacing: "0.2em", color: C.textDim, textTransform: "uppercase", marginBottom: "0.4rem", fontFamily: "JetBrains Mono" }}>{label}</label>
      {children}
    </div>
  );
}

// ─── TABS ─────────────────────────────────────────────────────────────────────
function InventoryTab({ ingredients, onAdd, onAdjust }) {
  const C = useInvTheme();
  const inputStyle = getInputStyle(C);
  const btnPrimary = getBtnPrimary(C);
  const btnSecondary = getBtnSecondary(C);
  const stockStatus = getStockStatus(C);
  
  const [search, setSearch] = useState("");
  const filtered = ingredients.filter(i => i.name.toLowerCase().includes(search.toLowerCase()) || i.category.toLowerCase().includes(search.toLowerCase()));
  const lowStock = ingredients.filter(i => i.stock <= i.reorderPoint).length;

  return (
    <div style={{ animation: "invFadeIn 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <div style={{ fontFamily: "Cormorant Garamond", fontSize: "1.3rem", color: C.white, fontWeight: 300 }}>Raw Ingredient Stock</div>
          {lowStock > 0 && <div style={{ fontSize: "0.68rem", color: C.amber, fontFamily: "JetBrains Mono", marginTop: "0.2rem" }}>⚠ {lowStock} ingredient{lowStock > 1 ? "s" : ""} at or below reorder point</div>}
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search ingredients..." style={{ ...inputStyle, width: 200, padding: "0.5rem 0.75rem" }} data-testid="ingredient-search" />
          <button style={btnPrimary} className="inv-btn-hover" onClick={onAdd} data-testid="add-ingredient-btn">+ Add Ingredient</button>
        </div>
      </div>

      <div style={{ border: `1px solid ${C.border}`, overflow: "auto" }}>
        {/* Header */}
        <div style={{ display: "grid", gridTemplateColumns: "2.5fr 1.2fr 1fr 1.5fr 1fr 1fr 1fr", gap: "1px", background: C.bg, borderBottom: `1px solid ${C.border}`, padding: "0.6rem 1rem", minWidth: "900px" }}>
          {["Ingredient", "Category", "Stock", "Supplier", "Reorder At", "Health Canada", "Action"].map(h => (
            <div key={h} style={{ fontSize: "0.58rem", letterSpacing: "0.2em", color: C.textMuted, textTransform: "uppercase", fontFamily: "JetBrains Mono" }}>{h}</div>
          ))}
        </div>

        {filtered.map((ing, idx) => {
          const st = stockStatus(ing.stock, ing.reorderPoint);
          const fillPct = pct(ing.stock, ing.reorderPoint * 4);
          return (
            <div key={ing.id} className="inv-row-hover" style={{ display: "grid", gridTemplateColumns: "2.5fr 1.2fr 1fr 1.5fr 1fr 1fr 1fr", gap: "1px", padding: "0.85rem 1rem", borderBottom: `1px solid ${C.border}`, background: idx % 2 === 0 ? C.surface : "transparent", animation: `invSlideIn 0.3s ${idx * 0.03}s both`, minWidth: "900px" }} data-testid={`ingredient-row-${ing.id}`}>
              <div>
                <div style={{ fontSize: "0.82rem", color: C.white, fontFamily: "Cormorant Garamond", fontWeight: 400 }}>{ing.name}</div>
                <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: "JetBrains Mono", marginTop: "0.2rem" }}>{ing.id}</div>
              </div>
              <div style={{ fontSize: "0.72rem", color: C.textDim, fontFamily: "JetBrains Mono", alignSelf: "center" }}>{ing.category}</div>
              <div style={{ alignSelf: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.82rem", color: st.color, fontFamily: "JetBrains Mono", fontWeight: 400 }}>{ing.stock.toLocaleString()}</span>
                  <span style={{ fontSize: "0.6rem", color: C.textMuted, fontFamily: "JetBrains Mono" }}>{ing.unit}</span>
                </div>
                <div style={{ height: 2, background: C.border, marginTop: "0.3rem", borderRadius: 1, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${fillPct}%`, background: st.color, transition: "width 0.5s ease" }} />
                </div>
              </div>
              <div style={{ fontSize: "0.72rem", color: C.textDim, fontFamily: "JetBrains Mono", alignSelf: "center" }}>{ing.supplier}</div>
              <div style={{ fontSize: "0.72rem", color: C.textDim, fontFamily: "JetBrains Mono", alignSelf: "center" }}>{ing.reorderPoint.toLocaleString()} {ing.unit}</div>
              <div style={{ alignSelf: "center" }}>
                <Badge label={ing.healthCanada} color={ing.healthCanada === "Approved" ? C.greenBright : C.amber} />
              </div>
              <div style={{ alignSelf: "center", display: "flex", gap: "0.5rem" }}>
                <button onClick={() => onAdjust(ing)} style={{ ...btnSecondary, padding: "0.3rem 0.6rem", fontSize: "0.58rem" }} className="inv-btn-hover" data-testid={`adjust-btn-${ing.id}`}>Adjust</button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProductsTab({ products }) {
  const C = useInvTheme();
  const btnPrimary = getBtnPrimary(C);
  
  return (
    <div style={{ animation: "invFadeIn 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
        <div style={{ fontFamily: "Cormorant Garamond", fontSize: "1.3rem", color: C.white, fontWeight: 300 }}>Finished Product Stock</div>
        <button style={btnPrimary} className="inv-btn-hover" data-testid="new-production-btn">+ New Production Run</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1px", background: C.border }}>
        {products.map((p, i) => {
          const available = p.stock - p.allocated;
          const statusColor = p.status === "Active" ? C.greenBright : p.status === "Low Stock" ? C.amber : C.redBright;
          return (
            <div key={p.id} style={{ background: C.surface, padding: "1.25rem", animation: `invFadeIn 0.4s ${i * 0.06}s both` }} data-testid={`product-card-${p.id}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
                <div>
                  <div style={{ fontFamily: "Cormorant Garamond", fontSize: "1rem", color: C.white, fontWeight: 400, lineHeight: 1.3 }}>{p.name}</div>
                  <div style={{ fontSize: "0.6rem", color: C.textMuted, fontFamily: "JetBrains Mono", marginTop: "0.3rem" }}>{p.batch}</div>
                </div>
                <Badge label={p.status.toUpperCase()} color={statusColor} />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                {[
                  ["Total Stock", p.stock],
                  ["Available", available],
                  ["Allocated", p.allocated],
                  ["Formula", p.formula],
                ].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontSize: "0.58rem", letterSpacing: "0.15em", color: C.textMuted, textTransform: "uppercase", fontFamily: "JetBrains Mono" }}>{k}</div>
                    <div style={{ fontSize: "0.9rem", color: k === "Available" ? C.gold : C.text, fontFamily: "JetBrains Mono", marginTop: "0.2rem" }}>{v}</div>
                  </div>
                ))}
              </div>

              <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: "0.75rem", display: "flex", justifyContent: "space-between" }}>
                <div style={{ fontSize: "0.6rem", color: C.textMuted, fontFamily: "JetBrains Mono" }}>
                  MFD {fmtDate(p.manufactured)}
                </div>
                <div style={{ fontSize: "0.6rem", color: C.textDim, fontFamily: "JetBrains Mono" }}>
                  EXP {fmtDate(p.expiry)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BatchesTab({ batches }) {
  const C = useInvTheme();
  const btnPrimary = getBtnPrimary(C);
  
  return (
    <div style={{ animation: "invFadeIn 0.3s ease" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
        <div style={{ fontFamily: "Cormorant Garamond", fontSize: "1.3rem", color: C.white, fontWeight: 300 }}>Batch Records & QC</div>
        <button style={btnPrimary} className="inv-btn-hover" data-testid="log-batch-btn">+ Log New Batch</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1px", background: C.border, overflow: "auto" }}>
        {/* Header */}
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.2fr 0.8fr 1fr 1fr 1fr 2fr", padding: "0.6rem 1.25rem", background: C.bg, minWidth: "900px" }}>
          {["Product", "Batch No.", "Qty", "Manufactured", "Expiry", "QC Status", "Notes"].map(h => (
            <div key={h} style={{ fontSize: "0.58rem", letterSpacing: "0.2em", color: C.textMuted, textTransform: "uppercase", fontFamily: "JetBrains Mono" }}>{h}</div>
          ))}
        </div>

        {batches.map((b, i) => {
          const qcColor = b.qcStatus === "Passed" ? C.greenBright : b.qcStatus === "Failed" ? C.redBright : C.amber;
          return (
            <div key={b.id} className="inv-row-hover" style={{ display: "grid", gridTemplateColumns: "1.5fr 1.2fr 0.8fr 1fr 1fr 1fr 2fr", padding: "0.85rem 1.25rem", background: i % 2 === 0 ? C.surface : C.bg, animation: `invSlideIn 0.3s ${i * 0.04}s both`, minWidth: "900px" }} data-testid={`batch-row-${b.id}`}>
              <div style={{ fontSize: "0.82rem", color: C.white, fontFamily: "Cormorant Garamond" }}>{b.product}</div>
              <div style={{ fontSize: "0.72rem", color: C.gold, fontFamily: "JetBrains Mono" }}>{b.batchNo}</div>
              <div style={{ fontSize: "0.72rem", color: C.text, fontFamily: "JetBrains Mono" }}>{b.qty} units</div>
              <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: "JetBrains Mono" }}>{fmtDate(b.manufactured)}</div>
              <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: "JetBrains Mono" }}>{fmtDate(b.expiry)}</div>
              <div><Badge label={b.qcStatus.toUpperCase()} color={qcColor} /></div>
              <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: "JetBrains Mono", lineHeight: 1.5 }}>{b.notes}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AlertsTab({ ingredients, products }) {
  const C = useInvTheme();
  const btnSecondary = getBtnSecondary(C);
  
  const lowIng = ingredients.filter(i => i.stock <= i.reorderPoint);
  const pendingHC = ingredients.filter(i => i.healthCanada === "Pending");
  const lowProd = products.filter(p => p.status === "Low Stock" || p.status === "Out of Stock");

  const AlertItem = ({ icon, title, detail, color, action }) => (
    <div style={{ display: "flex", alignItems: "flex-start", gap: "1rem", padding: "1rem 1.25rem", background: C.surface, border: `1px solid ${C.border}`, borderLeft: `3px solid ${color}`, animation: "invFadeIn 0.3s ease" }}>
      <span style={{ fontSize: "1rem", marginTop: "0.1rem" }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: "0.82rem", color: C.white, fontFamily: "Cormorant Garamond", fontWeight: 400 }}>{title}</div>
        <div style={{ fontSize: "0.68rem", color: C.textDim, fontFamily: "JetBrains Mono", marginTop: "0.2rem" }}>{detail}</div>
      </div>
      {action && <button style={{ ...btnSecondary, padding: "0.3rem 0.75rem", fontSize: "0.6rem", alignSelf: "center" }} className="inv-btn-hover">{action}</button>}
    </div>
  );

  return (
    <div style={{ animation: "invFadeIn 0.3s ease" }}>
      <div style={{ fontFamily: "Cormorant Garamond", fontSize: "1.3rem", color: C.white, fontWeight: 300, marginBottom: "1.5rem" }}>
        Active Alerts <span style={{ fontSize: "0.9rem", color: C.textDim }}>({lowIng.length + pendingHC.length + lowProd.length})</span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {lowProd.map(p => (
          <AlertItem key={p.id} icon="📦" color={p.status === "Out of Stock" ? C.redBright : C.amber}
            title={`${p.status}: ${p.name}`}
            detail={`${p.stock} units remaining — ${p.allocated} allocated | Batch: ${p.batch}`}
            action="Schedule Production" />
        ))}
        {lowIng.map(i => (
          <AlertItem key={i.id} icon="⚗️" color={i.stock === 0 ? C.redBright : C.amber}
            title={`Low Stock: ${i.name}`}
            detail={`${i.stock} ${i.unit} remaining — reorder point is ${i.reorderPoint} ${i.unit} | Supplier: ${i.supplier}`}
            action="Reorder Now" />
        ))}
        {pendingHC.map(i => (
          <AlertItem key={i.id} icon="🏛️" color={C.amber}
            title={`Health Canada Pending: ${i.name}`}
            detail={`Approval status pending. Verify compliance before next production run.`}
            action="Check Status" />
        ))}
        {lowIng.length + pendingHC.length + lowProd.length === 0 && (
          <div style={{ textAlign: "center", padding: "3rem", color: C.textMuted, fontFamily: "JetBrains Mono", fontSize: "0.78rem" }}>
            ✓ No active alerts — all systems normal
          </div>
        )}
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function InventoryBatchTracking() {
  const { isLaVela, shortName } = useAdminBrand();
  const C = getThemeColors(isLaVela);
  const css = generateCss(C);
  const inputStyle = getInputStyle(C);
  const btnPrimary = getBtnPrimary(C);
  const btnSecondary = getBtnSecondary(C);
  
  const [activeTab, setActiveTab] = useState("inventory");
  const [ingredients, setIngredients] = useState(isLaVela ? LAVELA_INGREDIENTS : INITIAL_INGREDIENTS);
  const [products, setProducts] = useState(isLaVela ? LAVELA_PRODUCTS : INITIAL_PRODUCTS);
  const [batches, setBatches] = useState(isLaVela ? LAVELA_BATCHES : INITIAL_BATCHES);
  const [modal, setModal] = useState(null); // "add-ingredient" | "adjust-ingredient"
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem('reroots_token');
  const activeBrand = localStorage.getItem('admin_active_brand') || 'reroots';

  // Reset data when brand changes
  useEffect(() => {
    setIngredients(isLaVela ? LAVELA_INGREDIENTS : INITIAL_INGREDIENTS);
    setProducts(isLaVela ? LAVELA_PRODUCTS : INITIAL_PRODUCTS);
    setBatches(isLaVela ? LAVELA_BATCHES : INITIAL_BATCHES);
  }, [isLaVela]);

  // Load data from backend on mount
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // Fetch real products from existing API (filtered by brand)
        const prodRes = await axios.get(`${API}/products?brand=${activeBrand}`).catch(() => null);
        if (prodRes?.data?.length) {
          // Transform real products to match component's expected format
          const transformedProducts = prodRes.data.map((p, idx) => ({
            id: p.id || `SKU-${idx}`,
            name: p.name,
            batch: `RR-2026-${String(idx + 1).padStart(3, '0')}`,
            manufactured: new Date(Date.now() - Math.random() * 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            expiry: new Date(Date.now() + 730 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            stock: p.stock || 0,
            allocated: Math.floor((p.stock || 0) * 0.15),
            status: (p.stock || 0) === 0 ? "Out of Stock" : (p.stock || 0) < 50 ? "Low Stock" : "Active",
            formula: `F-${String(idx + 1).padStart(3, '0')}`
          }));
          setProducts(transformedProducts);
        }
      } catch (err) {
        console.log('Using initial data');
      }
      setLoading(false);
    };
    fetchData();
  }, []);

  const alertCount = ingredients.filter(i => i.stock <= i.reorderPoint).length +
    ingredients.filter(i => i.healthCanada === "Pending").length +
    products.filter(p => p.status !== "Active").length;

  const tabs = [
    { id: "inventory", label: "Raw Ingredients", icon: "⚗" },
    { id: "products", label: "Finished Products", icon: "◈" },
    { id: "batches", label: "Batch Records", icon: "◉" },
    { id: "alerts", label: `Alerts${alertCount > 0 ? ` (${alertCount})` : ""}`, icon: "◎" },
  ];

  const totalIngredientValue = ingredients.reduce((sum, i) => sum + i.stock * i.cost, 0);
  const lowStockCount = ingredients.filter(i => i.stock <= i.reorderPoint).length;
  const totalFinishedUnits = products.reduce((sum, p) => sum + p.stock, 0);
  const pendingQC = batches.filter(b => b.qcStatus === "In Review").length;

  const handleAddIngredient = async () => {
    if (!form.name || !form.stock) return;
    const newIng = {
      id: `ING-${String(ingredients.length + 1).padStart(3, "0")}`,
      name: form.name, supplier: form.supplier || "—", unit: form.unit || "g",
      stock: parseFloat(form.stock) || 0, reorderPoint: parseFloat(form.reorderPoint) || 0,
      cost: parseFloat(form.cost) || 0, category: form.category || "Other",
      healthCanada: form.healthCanada || "Pending", lastUpdated: new Date().toISOString().split("T")[0],
    };
    setIngredients(prev => [...prev, newIng]);
    
    // Save to backend
    try {
      await axios.post(`${API}/business/inventory/ingredients`, newIng, { headers: { Authorization: `Bearer ${token}` } });
    } catch (err) {
      console.log('Saved locally');
    }
    
    setModal(null); setForm({});
  };

  const handleAdjustStock = async () => {
    if (!form.adjustment) return;
    const newStock = Math.max(0, selected.stock + parseFloat(form.adjustment));
    setIngredients(prev => prev.map(i =>
      i.id === selected.id ? { ...i, stock: newStock, lastUpdated: new Date().toISOString().split("T")[0] } : i
    ));
    
    // Save adjustment to backend
    try {
      await axios.post(`${API}/business/inventory/ingredients/${selected.id}/adjust`, {
        adjustment: parseFloat(form.adjustment),
        reason: form.reason || "Manual adjustment",
        newStock
      }, { headers: { Authorization: `Bearer ${token}` } });
    } catch (err) {
      console.log('Saved locally');
    }
    
    setModal(null); setForm({}); setSelected(null);
  };

  return (
    <InvThemeContext.Provider value={C}>
      <div className="inv-module" style={{ minHeight: "100vh", background: C.bg, fontFamily: "Cormorant Garamond, serif", color: C.text }} data-testid="inventory-batch-tracking">
        <style>{css}</style>

        {/* Header */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "1.25rem 2rem", display: "flex", alignItems: "center", justifyContent: "space-between", background: isLaVela ? "linear-gradient(180deg, #0A3C3C 0%, transparent 100%)" : "linear-gradient(180deg, #0c0e14 0%, transparent 100%)", flexWrap: "wrap", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: "1rem", flexWrap: "wrap" }}>
            <span style={{ fontFamily: "Cormorant Garamond", fontSize: "1.4rem", letterSpacing: "0.2em", color: C.gold, fontWeight: 300 }}>{shortName}</span>
            <span style={{ fontSize: "0.58rem", letterSpacing: "0.35em", color: C.textMuted, fontFamily: "JetBrains Mono", textTransform: "uppercase" }}>Inventory System · Module 01</span>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", fontSize: "0.62rem", color: C.green, fontFamily: "JetBrains Mono", letterSpacing: "0.1em" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.greenBright, animation: "invPulse 2s infinite", boxShadow: `0 0 8px ${C.greenBright}` }} />
            SYSTEM ACTIVE · {new Date().toLocaleDateString("en-CA")}
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1px", background: C.border, borderBottom: `1px solid ${C.border}` }}>
          <StatCard label="Ingredient Stock Value" value={`$${totalIngredientValue.toLocaleString("en-CA", { maximumFractionDigits: 0 })}`} sub="CAD · all raw materials" />
          <StatCard label="Low / Critical Items" value={lowStockCount} sub="require reorder action" accent={lowStockCount > 0 ? C.amber : C.greenBright} pulse={lowStockCount > 0} />
          <StatCard label="Finished Units" value={totalFinishedUnits.toLocaleString()} sub="across all SKUs" />
          <StatCard label="QC In Review" value={pendingQC} sub="batch records pending" accent={pendingQC > 0 ? C.amber : C.greenBright} />
        </div>

        {/* Tabs */}
        <div style={{ borderBottom: `1px solid ${C.border}`, padding: "0 2rem", display: "flex", gap: "0", overflowX: "auto" }}>
          {tabs.map(t => (
            <button key={t.id} className="inv-tab-item" onClick={() => setActiveTab(t.id)}
              style={{ background: "none", border: "none", borderBottom: `2px solid ${activeTab === t.id ? C.gold : "transparent"}`, padding: "0.9rem 1.25rem", cursor: "pointer", color: activeTab === t.id ? C.gold : C.textDim, fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase", fontFamily: "JetBrains Mono", transition: "all 0.2s", display: "flex", alignItems: "center", gap: "0.5rem", whiteSpace: "nowrap" }}
              data-testid={`tab-${t.id}`}>
              <span style={{ opacity: 0.7 }}>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div style={{ padding: "2rem" }}>
          {loading && <div style={{ textAlign: "center", padding: "2rem", color: C.textDim }}>Loading...</div>}
          {!loading && activeTab === "inventory" && <InventoryTab ingredients={ingredients} onAdd={() => { setForm({}); setModal("add-ingredient"); }} onAdjust={(ing) => { setSelected(ing); setForm({}); setModal("adjust-ingredient"); }} />}
          {!loading && activeTab === "products" && <ProductsTab products={products} />}
          {!loading && activeTab === "batches" && <BatchesTab batches={batches} />}
          {!loading && activeTab === "alerts" && <AlertsTab ingredients={ingredients} products={products} />}
        </div>

        {/* Module Roadmap Footer */}
        <div style={{ borderTop: `1px solid ${C.border}`, padding: "1rem 2rem", display: "flex", gap: "1.5rem", background: C.surface, flexWrap: "wrap" }}>
          {[
            { label: "01 · Inventory", active: true },
            { label: "02 · CRM", active: false },
            { label: "03 · Orders", active: false },
            { label: "04 · Accounting", active: false },
          ].map(m => (
            <div key={m.label} style={{ fontSize: "0.6rem", letterSpacing: "0.15em", color: m.active ? C.gold : C.textMuted, fontFamily: "JetBrains Mono", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              {m.active && <div style={{ width: 4, height: 4, borderRadius: "50%", background: C.gold }} />}
              {m.label}
            </div>
          ))}
        </div>

        {/* Add Ingredient Modal */}
        {modal === "add-ingredient" && (
          <Modal title="Add Raw Ingredient" onClose={() => setModal(null)}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 1rem" }}>
              <div style={{ gridColumn: "1/-1" }}>
                <FormField label="Ingredient Name *"><input style={inputStyle} value={form.name || ""} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. PDRN Concentrate 2%" data-testid="ingredient-name-input" /></FormField>
              </div>
              <FormField label="Category"><select style={inputStyle} value={form.category || ""} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} data-testid="ingredient-category-select">
                <option value="">Select...</option>
                {["Active", "Humectant", "Lipid", "Peptide", "Retinoid", "Emollient", "Preservative", "Other"].map(c => <option key={c}>{c}</option>)}
              </select></FormField>
              <FormField label="Unit"><select style={inputStyle} value={form.unit || "g"} onChange={e => setForm(f => ({ ...f, unit: e.target.value }))} data-testid="ingredient-unit-select">
                {["g", "ml", "kg", "L", "units"].map(u => <option key={u}>{u}</option>)}
              </select></FormField>
              <FormField label="Current Stock *"><input style={inputStyle} type="number" value={form.stock || ""} onChange={e => setForm(f => ({ ...f, stock: e.target.value }))} placeholder="0" data-testid="ingredient-stock-input" /></FormField>
              <FormField label="Reorder Point"><input style={inputStyle} type="number" value={form.reorderPoint || ""} onChange={e => setForm(f => ({ ...f, reorderPoint: e.target.value }))} placeholder="0" /></FormField>
              <div style={{ gridColumn: "1/-1" }}>
                <FormField label="Supplier"><input style={inputStyle} value={form.supplier || ""} onChange={e => setForm(f => ({ ...f, supplier: e.target.value }))} placeholder="e.g. BioLab Korea" /></FormField>
              </div>
              <FormField label="Cost per unit (CAD)"><input style={inputStyle} type="number" step="0.01" value={form.cost || ""} onChange={e => setForm(f => ({ ...f, cost: e.target.value }))} placeholder="0.00" /></FormField>
              <FormField label="Health Canada Status"><select style={inputStyle} value={form.healthCanada || "Pending"} onChange={e => setForm(f => ({ ...f, healthCanada: e.target.value }))}>
                <option>Approved</option><option>Pending</option><option>Under Review</option>
              </select></FormField>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
              <button style={btnSecondary} onClick={() => setModal(null)}>Cancel</button>
              <button style={btnPrimary} className="inv-btn-hover" onClick={handleAddIngredient} data-testid="save-ingredient-btn">Add Ingredient</button>
            </div>
          </Modal>
        )}

        {/* Adjust Stock Modal */}
        {modal === "adjust-ingredient" && selected && (
          <Modal title={`Adjust Stock · ${selected.name}`} onClose={() => setModal(null)}>
            <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "1rem", marginBottom: "1.25rem", fontFamily: "JetBrains Mono", fontSize: "0.78rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div><span style={{ color: C.textMuted }}>Current Stock: </span><span style={{ color: C.gold }}>{selected.stock} {selected.unit}</span></div>
                <div><span style={{ color: C.textMuted }}>Reorder Point: </span><span style={{ color: C.text }}>{selected.reorderPoint} {selected.unit}</span></div>
              </div>
            </div>
            <FormField label="Adjustment Amount (use negative to reduce)">
              <input style={inputStyle} type="number" value={form.adjustment || ""} onChange={e => setForm(f => ({ ...f, adjustment: e.target.value }))} placeholder="e.g. +500 or -100" data-testid="adjustment-input" />
            </FormField>
            <FormField label="Reason">
              <select style={inputStyle} value={form.reason || ""} onChange={e => setForm(f => ({ ...f, reason: e.target.value }))} data-testid="adjustment-reason-select">
                <option value="">Select reason...</option>
                <option>New delivery received</option>
                <option>Used in production batch</option>
                <option>QC sample drawn</option>
                <option>Damaged / expired</option>
                <option>Inventory count correction</option>
              </select>
            </FormField>
            {form.adjustment && (
              <div style={{ background: C.bg, border: `1px solid ${C.border}`, padding: "0.75rem 1rem", marginBottom: "1rem", fontFamily: "JetBrains Mono", fontSize: "0.72rem", color: C.textDim }}>
                New stock will be: <span style={{ color: parseFloat(form.adjustment) > 0 ? C.greenBright : C.amber }}>
                  {Math.max(0, selected.stock + (parseFloat(form.adjustment) || 0))} {selected.unit}
                </span>
              </div>
            )}
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end" }}>
              <button style={btnSecondary} onClick={() => setModal(null)}>Cancel</button>
              <button style={btnPrimary} className="inv-btn-hover" onClick={handleAdjustStock} data-testid="confirm-adjustment-btn">Confirm Adjustment</button>
            </div>
          </Modal>
        )}
      </div>
    </InvThemeContext.Provider>
  );
}
