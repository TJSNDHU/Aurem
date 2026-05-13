/**
 * IncidentLedger.jsx — founder cockpit for the AUREM incident pipeline
 * (iter 322ff). Three panes:
 *
 *   1. Live ledger        — last 50 incidents with filters
 *   2. Detail drawer      — full row + triage summary + fix-step audit
 *   3. Fingerprint library — recurring patterns + known playbook each
 *
 * Route: /admin/incident-ledger
 */
import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Crown, ShieldAlert, AlertTriangle, CheckCircle2, Loader2,
  RefreshCw, ExternalLink, Wand2, BookOpen, X,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GREEN = "#67E8A0";
const RED = "#FF7676";
const AMBER = "#FFB36B";
const BLUE = "#6FB8FF";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 14,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
};

const SEV_COLOR = { P0: RED, P1: AMBER, P2: BLUE, P3: TEXT_DIM };
const STATUS_COLOR = {
  open: AMBER, triaged: BLUE, fixing: BLUE,
  resolved: GREEN, escalated: RED,
};

function authHeaders() {
  const token =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function safeJson(r) {
  try { return await r.json(); }
  catch { return { ok: false, error: `HTTP ${r.status}` }; }
}

export default function IncidentLedger() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ status: "", severity: "", category: "" });
  const [picked, setPicked] = useState(null);
  const [fingerprints, setFingerprints] = useState([]);
  const [showFps, setShowFps] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const qs = new URLSearchParams();
      qs.set("limit", "80");
      if (filter.status)   qs.set("status",   filter.status);
      if (filter.severity) qs.set("severity", filter.severity);
      if (filter.category) qs.set("category", filter.category);
      const r = await fetch(`${API}/api/incident/list?${qs}`, { headers: authHeaders() });
      const j = await safeJson(r);
      if (j.ok) setRows(j.rows || []); else setError(j.error || j.detail || "load failed");
    } catch (e) { setError(String(e)); }
    setLoading(false);
  }, [filter]);

  const loadFps = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/incident/fingerprints`, { headers: authHeaders() });
      const j = await safeJson(r);
      if (j.ok) setFingerprints(j.rows || []);
    } catch { /* soft */ }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadFps(); }, [loadFps]);
  useEffect(() => {
    const t = setInterval(() => { load(); loadFps(); }, 15_000);
    return () => clearInterval(t);
  }, [load, loadFps]);

  const triage = async (id) => {
    try {
      const r = await fetch(`${API}/api/incident/triage/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ auto_run_playbook: false }),
      });
      const j = await safeJson(r);
      if (j.ok) {
        if (picked && picked.incident_id === id) {
          const fresh = await fetchOne(id);
          setPicked((p) => p ? { ...p, ...fresh } : p);
        }
        load();
      } else setError(j.detail || j.error || "triage failed");
    } catch (e) { setError(String(e)); }
  };

  const resolve = async (id) => {
    const note = window.prompt("Resolution note (optional):", "") || "";
    try {
      const r = await fetch(`${API}/api/incident/resolve/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ note, learn: true }),
      });
      const j = await safeJson(r);
      if (j.ok) {
        setPicked(null);
        load(); loadFps();
      } else setError(j.detail || j.error || "resolve failed");
    } catch (e) { setError(String(e)); }
  };

  const fetchOne = async (id) => {
    const r = await fetch(`${API}/api/incident/status/${id}`, { headers: authHeaders() });
    return await safeJson(r);
  };

  // KPIs
  const kpi = {
    total:    rows.length,
    open:     rows.filter((r) => r.status === "open").length,
    triaged:  rows.filter((r) => r.status === "triaged").length,
    resolved: rows.filter((r) => r.status === "resolved").length,
    p0:       rows.filter((r) => r.severity === "P0").length,
  };

  return (
    <div data-testid="incident-ledger"
         style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <ShieldAlert size={24} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Incident Ledger</h1>
          </div>
          <p style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>
            iter 322ff · Live pipeline · auto-refresh 15s
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button data-testid="toggle-fps" onClick={() => setShowFps((v) => !v)} style={btn(false)}>
            <BookOpen size={12} /> {showFps ? "Hide" : "Show"} fingerprints
          </button>
          <button data-testid="refresh-btn" onClick={() => { load(); loadFps(); }} style={btn(false)}>
            <RefreshCw size={12} /> Refresh
          </button>
          <button onClick={() => navigate("/admin/boardroom")} style={btn(false)}>← Back</button>
        </div>
      </div>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 14 }}>
        <Kpi label="Total"     val={kpi.total} />
        <Kpi label="Open"      val={kpi.open}     color={AMBER} />
        <Kpi label="Triaged"   val={kpi.triaged}  color={BLUE} />
        <Kpi label="Resolved"  val={kpi.resolved} color={GREEN} />
        <Kpi label="P0"        val={kpi.p0}       color={RED} />
      </div>

      {/* Filters */}
      <div style={{ ...GLASS, padding: 12, marginBottom: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>Filter:</span>
        <Select label="Status"   value={filter.status}   onChange={(v) => setFilter({ ...filter, status: v })}
                opts={["", "open", "triaged", "fixing", "resolved", "escalated"]} />
        <Select label="Severity" value={filter.severity} onChange={(v) => setFilter({ ...filter, severity: v })}
                opts={["", "P0", "P1", "P2", "P3"]} />
        <Select label="Category" value={filter.category} onChange={(v) => setFilter({ ...filter, category: v })}
                opts={["", "transient_502", "timeout", "backend_5xx", "frontend_crash",
                       "frontend_unhandled_rejection", "tool_exception", "route_missing",
                       "db_conn", "rate_limit_hit", "unknown"]} />
      </div>

      {error && (
        <div style={{ ...GLASS, padding: 12, color: RED, marginBottom: 12 }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Layout: ledger + optional drawer or fingerprints */}
      <div style={{ display: "grid", gridTemplateColumns: picked || showFps ? "1fr 420px" : "1fr", gap: 12 }}>
        <div style={{ ...GLASS, padding: 0, maxHeight: "70vh", overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ position: "sticky", top: 0, background: "#0A0A12", zIndex: 1 }}>
                {["Time", "Severity", "Category", "Title", "Source", "Status", "Occ"].map((h) => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={7} style={{ padding: 20, color: TEXT_DIM }}>
                  <Loader2 size={14} className="spin" /> loading…
                </td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 20, color: TEXT_DIM, textAlign: "center" }}>
                  No incidents in window — pipeline quiet ✓
                </td></tr>
              )}
              {rows.map((r) => (
                <tr key={r.incident_id}
                    data-testid={`inc-row-${r.incident_id}`}
                    onClick={() => setPicked(r)}
                    style={{
                      cursor: "pointer",
                      background: picked?.incident_id === r.incident_id ? "rgba(212,175,55,0.10)" : "transparent",
                      borderTop: `1px solid rgba(212,175,55,0.08)`,
                    }}>
                  <td style={td}>{(r.last_seen || r.created_at || "").slice(11, 19)}</td>
                  <td style={{ ...td, color: SEV_COLOR[r.severity] || TEXT_DIM, fontWeight: 700 }}>
                    {r.severity}
                  </td>
                  <td style={{ ...td, color: TEXT }}>{r.category}</td>
                  <td style={{ ...td, color: TEXT, maxWidth: 380,
                                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.title}
                  </td>
                  <td style={{ ...td, color: TEXT_DIM }}>{r.source}</td>
                  <td style={{ ...td, color: STATUS_COLOR[r.status] || TEXT_DIM, fontWeight: 600 }}>
                    {r.status}
                  </td>
                  <td style={{ ...td, color: TEXT_DIM, textAlign: "right" }}>{r.occurrences || 1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Right pane: detail drawer or fingerprints */}
        {picked && (
          <DetailDrawer
            row={picked}
            onClose={() => setPicked(null)}
            onTriage={() => triage(picked.incident_id)}
            onResolve={() => resolve(picked.incident_id)}
          />
        )}
        {!picked && showFps && (
          <FingerprintsPane rows={fingerprints} />
        )}
      </div>

      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function Kpi({ label, val, color }) {
  return (
    <div style={{ ...GLASS, padding: 14 }}>
      <div style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || TEXT, marginTop: 4 }}>{val}</div>
    </div>
  );
}

function Select({ label, value, onChange, opts }) {
  return (
    <label style={{ color: TEXT_DIM, fontSize: 11, display: "flex", alignItems: "center", gap: 6 }}>
      {label}
      <select data-testid={`filter-${label.toLowerCase()}`}
              value={value} onChange={(e) => onChange(e.target.value)}
              style={{
                background: "rgba(0,0,0,0.4)", color: TEXT,
                border: `1px solid ${BORDER}`, borderRadius: 8,
                padding: "4px 8px", fontSize: 12,
              }}>
        {opts.map((o) => <option key={o} value={o}>{o || "(any)"}</option>)}
      </select>
    </label>
  );
}

function DetailDrawer({ row, onClose, onTriage, onResolve }) {
  const tr = row.triage_summary || {};
  return (
    <div data-testid="incident-drawer" style={{ ...GLASS, padding: 14, maxHeight: "70vh", overflow: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Crown size={14} color={GOLD} />
          <span style={{ fontFamily: "ui-monospace,monospace", fontSize: 12, color: GOLD }}>
            {row.incident_id}
          </span>
        </div>
        <button data-testid="drawer-close" onClick={onClose} style={btn(false)}>
          <X size={12} />
        </button>
      </div>

      <div style={{ marginTop: 10, fontSize: 14, fontWeight: 600 }}>{row.title}</div>
      <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 4 }}>
        {row.category} · {row.severity} · {row.status} · seen {row.occurrences || 1}×
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button data-testid="drawer-triage" onClick={onTriage} style={btn(true)}>
          <Wand2 size={12} /> Run triage
        </button>
        {row.status !== "resolved" && (
          <button data-testid="drawer-resolve" onClick={onResolve} style={btn(false)}>
            <CheckCircle2 size={12} /> Mark resolved
          </button>
        )}
      </div>

      {Object.keys(tr).length > 0 && (
        <>
          <SectionLabel>Triage</SectionLabel>
          <Pre data={tr} />
        </>
      )}

      {(row.fix_steps || []).length > 0 && (
        <>
          <SectionLabel>Fix steps ({row.fix_steps.length})</SectionLabel>
          <Pre data={row.fix_steps} />
        </>
      )}

      <SectionLabel>Detail</SectionLabel>
      <pre style={mono}>{row.detail}</pre>

      <SectionLabel>Metadata</SectionLabel>
      <Pre data={row.metadata || {}} />

      <div style={{ color: TEXT_DIM, fontSize: 10, marginTop: 12, fontFamily: "ui-monospace,monospace" }}>
        fingerprint: {row.fingerprint} · created {(row.created_at || "").slice(0, 19)}
      </div>
    </div>
  );
}

function FingerprintsPane({ rows }) {
  return (
    <div style={{ ...GLASS, padding: 14, maxHeight: "70vh", overflow: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <BookOpen size={14} color={GOLD} />
        <span style={{ fontSize: 13, fontWeight: 600 }}>Fingerprint library</span>
        <span style={{ color: TEXT_DIM, fontSize: 11 }}>· {rows.length} patterns</span>
      </div>
      {rows.length === 0 ? (
        <div style={{ color: TEXT_DIM, fontSize: 12, padding: 8 }}>
          No patterns yet — resolve some incidents to seed the library.
        </div>
      ) : rows.map((r) => (
        <div key={r.fingerprint}
             data-testid={`fp-${r.fingerprint}`}
             style={{ padding: 8, borderBottom: `1px solid rgba(212,175,55,0.06)`, fontSize: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: TEXT, fontWeight: 600 }}>{r.category}</span>
            <span style={{ color: r.known_playbook ? GREEN : TEXT_DIM }}>
              {r.total_count}× · {r.known_playbook || "no playbook"}
            </span>
          </div>
          <div style={{ color: TEXT_DIM, fontSize: 10,
                          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {r.signature}
          </div>
        </div>
      ))}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{ color: TEXT_DIM, fontSize: 10, textTransform: "uppercase",
                    letterSpacing: 0.4, marginTop: 12, marginBottom: 4 }}>
      {children}
    </div>
  );
}

function Pre({ data }) {
  return (
    <pre style={mono}>{JSON.stringify(data, null, 2)}</pre>
  );
}

const mono = {
  margin: 0, padding: 10, borderRadius: 8,
  background: "rgba(0,0,0,0.4)", border: `1px solid ${BORDER}`,
  color: TEXT, fontSize: 11.5, lineHeight: 1.5,
  whiteSpace: "pre-wrap", wordBreak: "break-word",
  maxHeight: 240, overflow: "auto",
  fontFamily: "ui-monospace,monospace",
};
const th = { textAlign: "left", padding: "10px 12px", fontSize: 11,
              color: TEXT_DIM, textTransform: "uppercase", letterSpacing: 0.4,
              borderBottom: `1px solid ${BORDER}` };
const td = { padding: "8px 12px", fontSize: 12 };

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 10px", fontSize: 11.5,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
