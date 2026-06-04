/**
 * CampaignHealthPage.jsx — iter D-59
 *
 * Admin page that shows the live health of every component the
 * marketing campaign depends on, plus a one-click + "Fix All"
 * autonomous repair loop.
 *
 * Backend: services/campaign_health.py + services/campaign_autofix.py.
 *
 * Polling: every 30 s — light read, single Mongo round-trip per row.
 * Founder can also press "Refresh" for an instant pull.
 */
import React, { useEffect, useState, useCallback } from "react";
import { RefreshCw, Wrench, CheckCircle2, AlertTriangle,
         XCircle, Activity, ChevronDown, ChevronRight,
         Sparkles } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";

function adminHeaders() {
  let token = "";
  try {
    token = sessionStorage.getItem("platform_token") ||
            localStorage.getItem("platform_token") ||
            localStorage.getItem("aurem_admin_token") ||
            sessionStorage.getItem("aurem_admin_token") ||
            localStorage.getItem("token") ||
            "";
  } catch { /* ignore */ }
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const TINT = {
  green:  { bg: "rgba(74,222,128,0.10)", border: "rgba(74,222,128,0.30)",
             text: "#4ade80", icon: <CheckCircle2 size={13} /> },
  yellow: { bg: "rgba(255,200,87,0.10)", border: "rgba(255,200,87,0.30)",
             text: "#FFC857", icon: <AlertTriangle size={13} /> },
  red:    { bg: "rgba(255,96,96,0.10)",  border: "rgba(255,96,96,0.30)",
             text: "#FF6060", icon: <XCircle size={13} /> },
};


function StatusRow({ row, onAutofix, fixResult, expanded, onToggle, busy }) {
  const tint = TINT[row.status] || TINT.red;
  return (
    <div data-testid={`campaign-row-${row.component}`}
         style={{ border: `1px solid ${tint.border}`,
                  background: tint.bg, borderRadius: 4,
                  padding: "10px 12px", marginBottom: 8 }}>
      <div onClick={onToggle}
           style={{ display: "flex", alignItems: "center", gap: 10,
                    cursor: "pointer" }}>
        {expanded
          ? <ChevronDown size={12} style={{ color: tint.text }} />
          : <ChevronRight size={12} style={{ color: tint.text }} />}
        <span style={{ color: tint.text, display: "inline-flex",
                        alignItems: "center", gap: 4 }}>
          {tint.icon}
        </span>
        <strong style={{ color: "#F0EDE8", fontSize: 13,
                          fontFamily: "'JetBrains Mono', monospace",
                          minWidth: 160 }}>
          {row.component}
        </strong>
        <span style={{ color: tint.text, fontSize: 12 }}>
          {row.headline}
        </span>
        {row.autofix && (
          <button onClick={(e) => { e.stopPropagation(); onAutofix(row.autofix); }}
                  data-testid={`campaign-autofix-${row.component}`}
                  disabled={busy}
                  style={{ marginLeft: "auto",
                           padding: "4px 10px",
                           background: "rgba(255,107,0,0.10)",
                           border: "1px solid rgba(255,107,0,0.40)",
                           color: "#FF8C35",
                           borderRadius: 4, fontSize: 11,
                           cursor: busy ? "wait" : "pointer",
                           display: "inline-flex",
                           alignItems: "center", gap: 5 }}>
            <Wrench size={11} /> Autofix
          </button>
        )}
      </div>

      {expanded && (
        <div style={{ marginTop: 8, paddingLeft: 22, fontSize: 11.5,
                       color: "#a1958a",
                       fontFamily: "'JetBrains Mono', monospace" }}>
          <div>{row.detail || "—"}</div>
          {row.issue && (
            <div style={{ marginTop: 4, color: tint.text }}>
              issue: {row.issue}
            </div>
          )}
          {fixResult && (
            <div data-testid={`campaign-fix-result-${row.component}`}
                 style={{ marginTop: 8, padding: 8,
                          background: fixResult.fixed
                            ? "rgba(74,222,128,0.08)"
                            : "rgba(255,96,96,0.08)",
                          border: `1px solid ${fixResult.fixed
                            ? "rgba(74,222,128,0.30)"
                            : "rgba(255,96,96,0.30)"}`,
                          borderRadius: 4,
                          color: fixResult.fixed ? "#4ade80" : "#FF6060" }}>
              <strong>
                {fixResult.fixed ? "✅ Fixed" : "❌ Not fixed"}
              </strong>
              {" — "}
              {fixResult.action_taken}
              <div style={{ color: "#a1958a", marginTop: 2 }}>
                result: {fixResult.result}
              </div>
              {fixResult.residual_issue && !fixResult.fixed && (
                <div style={{ color: "#FF6060", marginTop: 2 }}>
                  residual: {fixResult.residual_issue}
                </div>
              )}
              {fixResult.requires_human && fixResult.human_hint && (
                <div style={{ color: "#FFC857", marginTop: 4 }}>
                  ⚠ requires founder: {fixResult.human_hint}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


export default function CampaignHealthPage() {
  const [report, setReport]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy]       = useState(false);
  const [expanded, setExpanded] = useState({});
  const [fixes, setFixes]     = useState({});  // component → fix result
  const [error, setError]     = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const r = await fetch(`${API}/api/admin/campaign/health`,
                              { headers: adminHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "load_failed");
      setReport(j);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [load]);

  async function runAutofix(tag) {
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/campaign/autofix/${tag}`,
                              { method: "POST", headers: adminHeaders() });
      const j = await r.json();
      // Map result back to its component name (j.component) so the
      // expanded row renders the outcome.
      setFixes(prev => ({ ...prev, [j.component || tag]: j }));
    } catch (e) {
      setFixes(prev => ({ ...prev, [tag]:
        { fixed: false, action_taken: "request_failed",
          result: String(e.message || e),
          residual_issue: "network", requires_human: true,
          human_hint: "Check backend availability" } }));
    } finally {
      setBusy(false);
      load();
    }
  }

  async function runAutofixAll() {
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/campaign/autofix-all`,
                              { method: "POST", headers: adminHeaders() });
      const j = await r.json();
      const out = {};
      for (const fix of (j.results || [])) {
        out[fix.component] = fix;
      }
      setFixes(prev => ({ ...prev, ...out }));
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
      load();
    }
  }

  const sum = report?.summary || { green: 0, yellow: 0, red: 0 };

  return (
    <div data-testid="campaign-health-page"
         style={{ padding: "24px 28px", maxWidth: 1100, margin: "0 auto",
                  color: "#F0EDE8" }}>

      <div style={{ display: "flex", alignItems: "center", gap: 12,
                     marginBottom: 18 }}>
        <Activity size={18} style={{ color: "#FF8C35" }} />
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                      color: "#E8C86A", margin: 0 }}>
          Campaign Health
        </h1>
        <span style={{ marginLeft: "auto", display: "inline-flex",
                        gap: 10, fontSize: 11,
                        fontFamily: "'JetBrains Mono', monospace" }}>
          <span style={{ color: "#4ade80" }}>● {sum.green} green</span>
          <span style={{ color: "#FFC857" }}>● {sum.yellow} yellow</span>
          <span style={{ color: "#FF6060" }}>● {sum.red} red</span>
        </span>
        <button onClick={load}
                data-testid="campaign-health-refresh"
                disabled={loading}
                style={{ background: "rgba(255,255,255,0.04)",
                          border: "1px solid var(--dash-border)",
                          color: "#a1958a", padding: "6px 12px",
                          borderRadius: 4, fontSize: 11,
                          cursor: loading ? "wait" : "pointer",
                          display: "inline-flex", alignItems: "center",
                          gap: 5 }}>
          <RefreshCw size={12}
                      className={loading ? "aurem-anim-spin" : ""} />
          Refresh
        </button>
        <button onClick={runAutofixAll}
                data-testid="campaign-autofix-all"
                disabled={busy}
                style={{ background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                          border: "none", color: "#fff",
                          padding: "6px 14px",
                          borderRadius: 4, fontSize: 12, fontWeight: 500,
                          cursor: busy ? "wait" : "pointer",
                          display: "inline-flex", alignItems: "center",
                          gap: 6 }}>
          <Sparkles size={13} /> Fix All
        </button>
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 14, color: "#FF6060",
                       background: "rgba(255,96,96,0.08)",
                       border: "1px solid rgba(255,96,96,0.30)",
                       borderRadius: 4, fontSize: 12 }}>
          {error}
        </div>
      )}

      {report && report.rows && report.rows.map(row => (
        <StatusRow key={row.component}
                    row={row}
                    expanded={!!expanded[row.component]}
                    onToggle={() => setExpanded(e =>
                      ({ ...e, [row.component]: !e[row.component] }))}
                    fixResult={fixes[row.component]}
                    onAutofix={runAutofix}
                    busy={busy} />
      ))}

      {report && (
        <div style={{ marginTop: 14, fontSize: 10, color: "#a1958a",
                       fontFamily: "'JetBrains Mono', monospace" }}>
          generated at {report.generated_at} · auto-refresh 30s
        </div>
      )}
    </div>
  );
}
