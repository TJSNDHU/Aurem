/**
 * AdminCaseStudy — Generate, Download, Email board-ready business review PDFs
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /admin/case-study
 * Access: super_admin
 *
 *   1. Search/pick a tenant
 *   2. Choose period (monthly / quarterly / custom)
 *   3. Preview JSON → confirm → Generate PDF
 *   4. Download or Email to customer via Resend
 */
import React, { useState, useEffect, useCallback } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import { FileText, Send, Download, Search, Sparkles, RefreshCw, Activity, Zap } from "lucide-react";
import { BACKEND_URL } from "../lib/api";

const API = BACKEND_URL;

export default function AdminCaseStudy() {
  const { apiJson, token } = useAuthFetch();
  const [tenants, setTenants] = useState([]);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [reportType, setReportType] = useState("monthly");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [preview, setPreview] = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [systemAudits, setSystemAudits] = useState([]);
  const [lastAudit, setLastAudit] = useState(null);
  const [auditEmail, setAuditEmail] = useState("");
  const [auditBusy, setAuditBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const G = "#C9A227";

  const push = useCallback((msg, t = "info") => {
    setToast({ msg, t }); setTimeout(() => setToast(null), 3500);
  }, []);

  const loadTenants = useCallback(async () => {
    try {
      const d = await apiJson(`/api/admin/case-study/tenants${q ? `?q=${encodeURIComponent(q)}` : ""}`);
      setTenants(d.tenants || []);
    } catch (e) { push(`Tenants load failed: ${e.message}`, "error"); }
  }, [apiJson, q, push]);

  const loadHistory = useCallback(async () => {
    try {
      const d = await apiJson(`/api/admin/case-study/list?limit=30`);
      setHistory(d.reports || []);
    } catch (e) { /* silent */ }
  }, [apiJson]);

  const loadSystemAudits = useCallback(async () => {
    try {
      const d = await apiJson(`/api/admin/case-study/system-audit/list?limit=12`);
      setSystemAudits(d.reports || []);
    } catch (e) { /* silent */ }
  }, [apiJson]);

  useEffect(() => { loadTenants(); loadHistory(); loadSystemAudits(); }, [loadTenants, loadHistory, loadSystemAudits]);

  const generateSystemAudit = async () => {
    setAuditBusy(true);
    try {
      const d = await apiJson("/api/admin/case-study/system-audit", { method: "POST" });
      setLastAudit(d);
      await loadSystemAudits();
      push(`Heartbeat pulse captured · ${d.report_id}`, "success");
    } catch (e) { push(`Audit failed: ${e.message}`, "error"); }
    setAuditBusy(false);
  };

  const emailSystemAudit = async () => {
    const to = (auditEmail || "").trim();
    if (!to) return push("Enter recipient email", "error");
    setAuditBusy(true);
    try {
      const d = await apiJson("/api/admin/case-study/system-audit/email", { method: "POST", body: { to_email: to } });
      if (d.ok) {
        push(`Heartbeat emailed to ${d.to}`, "success");
        await loadSystemAudits();
      } else {
        push(`Email failed: ${d.error}`, "error");
      }
    } catch (e) { push(`Email failed: ${e.message}`, "error"); }
    setAuditBusy(false);
  };

  const downloadSystemAudit = async (reportId) => {
    try {
      const r = await fetch(`${API}/api/admin/case-study/system-audit/download/${reportId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: "omit",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${reportId}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      push("Downloading…", "success");
    } catch (e) { push(`Download failed: ${e.message}`, "error"); }
  };

  const buildBody = () => ({
    report_type: reportType,
    target_email: selected?.email,
    target_name: selected?.name,
    target_bin: selected?.bin,
    ...(reportType === "custom" ? { period_start: customStart, period_end: customEnd } : {}),
  });

  const doPreview = async () => {
    if (!selected) return push("Pick a tenant first", "error");
    setBusy(true);
    try {
      const d = await apiJson("/api/admin/case-study/preview", { method: "POST", body: buildBody() });
      setPreview(d.preview);
      push("Preview loaded", "success");
    } catch (e) { push(`Preview failed: ${e.message}`, "error"); }
    setBusy(false);
  };

  const doGenerate = async () => {
    if (!selected) return push("Pick a tenant first", "error");
    setBusy(true);
    try {
      const d = await apiJson("/api/admin/case-study/generate", { method: "POST", body: buildBody() });
      setLastReport(d);
      await loadHistory();
      push(`PDF built · ${d.report_id}`, "success");
    } catch (e) { push(`Generate failed: ${e.message}`, "error"); }
    setBusy(false);
  };

  const doDownload = async (reportId) => {
    // Use fetch directly so we can stream with Bearer
    try {
      const r = await fetch(`${API}/api/case-study/download/${reportId}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: "omit",
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${reportId}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      push("Downloading…", "success");
    } catch (e) { push(`Download failed: ${e.message}`, "error"); }
  };

  const doEmail = async (reportId) => {
    if (!window.confirm("Email this report to the customer?")) return;
    try {
      const d = await apiJson("/api/admin/case-study/email", { method: "POST", body: { report_id: reportId } });
      push(`Emailed to ${d.to}`, "success");
      await loadHistory();
    } catch (e) { push(`Email failed: ${e.message}`, "error"); }
  };

  // ═══ styles (matches Sentinel / ORA) ═══
  const s = {
    root: { minHeight: "100vh", padding: "24px 28px", background: "#050507", color: "#E4DDD3", fontFamily: "'Jost', sans-serif" },
    title: { fontFamily: "'Cinzel', serif", fontSize: 22, color: G, letterSpacing: ".12em" },
    sub: { fontSize: 11, color: "#7a7a7a", letterSpacing: ".08em", textTransform: "uppercase", marginTop: 4 },
    grid2: { display: "grid", gridTemplateColumns: "380px 1fr", gap: 18, marginTop: 22 },
    card: { background: "rgba(15,18,28,0.6)", border: `1px solid rgba(201,162,39,0.18)`, borderRadius: 10, padding: 16, backdropFilter: "blur(16px)" },
    cardHead: { fontSize: 10, color: G, letterSpacing: ".14em", textTransform: "uppercase", fontWeight: 700, marginBottom: 12 },
    input: { width: "100%", background: "#0c0c0d", color: "#e4ddd3", border: "1px solid #222", borderRadius: 4, padding: "8px 10px", fontSize: 12, fontFamily: "'Jost', sans-serif" },
    select: { background: "#0c0c0d", color: "#e4ddd3", border: "1px solid #222", borderRadius: 4, padding: "8px 10px", fontSize: 12, fontFamily: "'Jost', sans-serif" },
    tenantRow: (a) => ({ padding: "8px 10px", borderRadius: 3, cursor: "pointer", background: a ? "rgba(201,162,39,0.1)" : "transparent", border: `1px solid ${a ? G + "40" : "transparent"}`, marginBottom: 4, fontSize: 11.5 }),
    btnGold: { background: G, color: "#0c0c0d", border: "none", padding: "10px 16px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase", width: "100%", marginTop: 8 },
    btnGhost: (c = "#7a7a7a") => ({ background: "transparent", border: `1px solid ${c}50`, color: c, padding: "7px 12px", borderRadius: 3, cursor: "pointer", fontSize: 10.5, letterSpacing: ".06em", marginRight: 8 }),
    kpi: { padding: 12, background: "rgba(20,20,26,0.6)", borderRadius: 6, border: `1px solid rgba(201,162,39,0.12)` },
    kpiLabel: { fontSize: 9, letterSpacing: ".15em", textTransform: "uppercase", color: "#7a7a7a", marginBottom: 6 },
    kpiValue: { fontFamily: "'Cinzel', serif", fontSize: 22, color: "#fff", lineHeight: 1 },
  };

  return (
    <div style={s.root} data-testid="admin-case-study">
      <div style={s.title}>◆ Case Study Builder</div>
      <div style={s.sub}>Board-ready business reviews · Real telemetry · AI-powered outlook</div>

      {/* ═══════════════ HEARTBEAT OF AUREM — System Audit ═══════════════ */}
      <div style={{ ...s.card, marginTop: 22, background: 'linear-gradient(135deg, rgba(201,162,39,0.08), rgba(15,18,28,0.6))', border: `1.5px solid ${G}35`, position: 'relative', overflow: 'hidden' }} data-testid="heartbeat-panel">
        <div style={{ position: 'absolute', top: -30, right: -30, width: 160, height: 160, borderRadius: '50%', background: `radial-gradient(${G}22, transparent 70%)`, pointerEvents: 'none' }} />
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20, position: 'relative', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 280 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#7EC8A0', boxShadow: '0 0 8px #7EC8A0', animation: 'pulse 2s infinite' }} />
              <div style={{ fontSize: 9.5, letterSpacing: '.2em', color: '#7EC8A0', textTransform: 'uppercase', fontWeight: 700 }}>LIVE · Monthly Auto-Heartbeat Active</div>
            </div>
            <div style={{ fontFamily: "'Cinzel', serif", fontSize: 20, color: '#fff', letterSpacing: 0.5, marginBottom: 4 }}>
              The Heartbeat of <span style={{ color: G }}>AUREM</span>
            </div>
            <div style={{ fontSize: 11, color: '#aaa', lineHeight: 1.6, maxWidth: 560 }}>
              One-click platform self-audit · 10-page PDF from live codebase, schedulers, Stripe catalog,
              integrations, risk register, and 3-scenario future outlook. Auto-emailed on the 1st of
              every month at 09:00 UTC.
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220 }}>
            <button onClick={generateSystemAudit} disabled={auditBusy} data-testid="heartbeat-pulse-btn"
              style={{ ...s.btnGold, marginTop: 0, padding: '10px 18px', opacity: auditBusy ? 0.5 : 1 }}>
              <Zap size={12} style={{ display: 'inline', marginRight: 6 }} />
              {auditBusy ? 'Pulsing…' : 'Pulse Heartbeat Now'}
            </button>
            <div style={{ display: 'flex', gap: 6 }}>
              <input type="email" value={auditEmail} onChange={(e) => setAuditEmail(e.target.value)}
                placeholder="recipient@email.com" data-testid="heartbeat-email-input"
                style={{ ...s.input, fontSize: 11, padding: '8px 10px' }} />
              <button onClick={emailSystemAudit} disabled={auditBusy} data-testid="heartbeat-email-btn"
                style={{ ...s.btnGhost('#7EC8A0'), padding: '8px 12px', marginRight: 0, whiteSpace: 'nowrap' }}>
                <Send size={11} /> Email
              </button>
            </div>
          </div>
        </div>

        {lastAudit && (
          <div style={{ marginTop: 16, paddingTop: 14, borderTop: `1px solid ${G}25`, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))', gap: 10 }} data-testid="heartbeat-last-stats">
            {[
              { l: 'LOC', v: lastAudit.summary.total_loc },
              { l: 'Routers', v: lastAudit.summary.backend_routers },
              { l: 'Services', v: lastAudit.summary.backend_services },
              { l: 'Frontend', v: lastAudit.summary.frontend_pages },
              { l: 'Endpoints', v: lastAudit.summary.total_endpoints },
              { l: 'SKUs', v: lastAudit.summary.catalog_skus },
              { l: 'Schedulers', v: lastAudit.summary.schedulers },
              { l: 'Integrations', v: lastAudit.summary.integrations },
            ].map((k) => (
              <div key={k.l} style={{ background: 'rgba(0,0,0,0.25)', padding: '8px 10px', borderRadius: 4, border: `1px solid rgba(201,162,39,0.1)` }}>
                <div style={{ fontSize: 8.5, letterSpacing: '.2em', color: '#888', textTransform: 'uppercase', fontWeight: 600, marginBottom: 3 }}>{k.l}</div>
                <div style={{ fontFamily: "'Cinzel', serif", fontSize: 16, color: G, lineHeight: 1 }}>{k.v}</div>
              </div>
            ))}
            <div style={{ gridColumn: '1 / -1', marginTop: 4 }}>
              <button onClick={() => downloadSystemAudit(lastAudit.report_id)} style={s.btnGhost(G)} data-testid="heartbeat-download-last">
                <Download size={11} style={{ display: 'inline', marginRight: 4 }} /> Download Latest Heartbeat PDF
              </button>
            </div>
          </div>
        )}

        {systemAudits.length > 0 && (
          <details style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${G}20` }} data-testid="heartbeat-history-toggle">
            <summary style={{ fontSize: 10, color: G, letterSpacing: '.15em', textTransform: 'uppercase', cursor: 'pointer', fontWeight: 700 }}>
              Past Heartbeats · {systemAudits.length}
            </summary>
            <div style={{ maxHeight: 220, overflowY: 'auto', marginTop: 10 }}>
              {systemAudits.map((r) => (
                <div key={r.report_id} style={{ padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.03)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }} data-testid={`heartbeat-row-${r.report_id}`}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontFamily: "'Cinzel', serif", fontSize: 11.5, color: '#fff' }}>{r.report_id}</div>
                    <div style={{ fontSize: 9.5, color: '#666' }}>
                      {r.summary_snapshot?.total_loc} LOC · {r.summary_snapshot?.total_endpoints} endpoints
                      {r.auto_month_key ? ` · auto-sent ${r.auto_month_key}` : ''}
                      {r.manual_emailed ? ` · emailed manually` : ''}
                    </div>
                  </div>
                  <button onClick={() => downloadSystemAudit(r.report_id)} style={{ ...s.btnGhost(G), padding: '4px 10px', marginRight: 0 }} data-testid={`heartbeat-dl-${r.report_id}`}>
                    PDF
                  </button>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(0.88); }
        }
      `}</style>

      {toast && (
        <div data-testid={`cs-toast-${toast.t}`} style={{ position: "fixed", top: 20, right: 20, zIndex: 1000,
          background: toast.t === "error" ? "#1a0808" : toast.t === "success" ? "#081508" : "#10101a",
          border: `1px solid ${toast.t === "error" ? "#7a2020" : "#2a5a2a"}`,
          padding: "10px 16px", borderRadius: 5, fontSize: 12 }}>{toast.msg}</div>
      )}

      <div style={s.grid2}>
        {/* ═══ LEFT — tenant picker + period ═══ */}
        <div>
          <div style={s.card}>
            <div style={s.cardHead}>Select Tenant</div>
            <div style={{ position: "relative", marginBottom: 10 }}>
              <Search size={12} style={{ position: "absolute", left: 10, top: 11, color: "#555" }} />
              <input
                placeholder="Search by email, name, BIN…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyUp={(e) => e.key === "Enter" && loadTenants()}
                style={{ ...s.input, paddingLeft: 26 }}
                data-testid="cs-tenant-search"
              />
            </div>
            <div style={{ maxHeight: 260, overflowY: "auto" }} data-testid="cs-tenant-list">
              {tenants.map((t) => (
                <div
                  key={t.email}
                  onClick={() => setSelected(t)}
                  style={s.tenantRow(selected?.email === t.email)}
                  data-testid={`cs-tenant-${t.email}`}
                >
                  <div style={{ color: "#e4ddd3", fontWeight: 600 }}>{t.name}</div>
                  <div style={{ color: "#666", fontSize: 10 }}>{t.email} · {t.bin || "no-bin"}</div>
                </div>
              ))}
              {tenants.length === 0 && <div style={{ fontSize: 11, color: "#555", padding: 12, textAlign: "center" }}>No tenants found.</div>}
            </div>
          </div>

          <div style={{ ...s.card, marginTop: 14 }}>
            <div style={s.cardHead}>Report Period</div>
            <select value={reportType} onChange={(e) => setReportType(e.target.value)} style={s.select} data-testid="cs-period-type">
              <option value="monthly">Monthly, last 30 days</option>
              <option value="quarterly">Quarterly, last 90 days</option>
              <option value="custom">Custom date range</option>
            </select>
            {reportType === "custom" && (
              <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} style={s.input} data-testid="cs-custom-start" />
                <input type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} style={s.input} data-testid="cs-custom-end" />
              </div>
            )}
            <button onClick={doPreview} disabled={busy} style={{ ...s.btnGold, background: "transparent", color: G, border: `1px solid ${G}60` }} data-testid="cs-preview-btn">
              <Sparkles size={12} style={{ display: "inline", marginRight: 6 }} />
              {busy ? "Loading…" : "Preview Data"}
            </button>
            <button onClick={doGenerate} disabled={busy || !selected} style={{ ...s.btnGold, opacity: busy || !selected ? 0.5 : 1 }} data-testid="cs-generate-btn">
              <FileText size={12} style={{ display: "inline", marginRight: 6 }} />
              {busy ? "Building…" : "Generate PDF"}
            </button>
          </div>
        </div>

        {/* ═══ RIGHT — preview / last report / history ═══ */}
        <div>
          {lastReport && (
            <div style={s.card}>
              <div style={s.cardHead}>Last Generated</div>
              <div style={{ fontSize: 13, color: "#fff", fontFamily: "'Cinzel', serif" }}>{lastReport.report_id}</div>
              <div style={{ fontSize: 11, color: "#888", margin: "4px 0 14px 0" }}>
                {lastReport.target?.name} · {lastReport.target?.email}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 14 }}>
                <div style={s.kpi}><div style={s.kpiLabel}>Uptime</div><div style={s.kpiValue}>{lastReport.summary.uptime_pct}%</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Hours Saved</div><div style={s.kpiValue}>{lastReport.summary.hours_saved}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>$ Saved</div><div style={s.kpiValue}>${lastReport.summary.dollars_saved}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Errors</div><div style={s.kpiValue}>{lastReport.summary.errors_captured}</div></div>
              </div>
              {lastReport.outlook_preview && (
                <div style={{ fontSize: 11, color: "#c4a54a", background: "rgba(201,162,39,0.06)", padding: "10px 12px", borderRadius: 4, border: `1px solid ${G}20`, marginBottom: 12, lineHeight: 1.55 }}>
                  <strong>AI Outlook:</strong> {lastReport.outlook_preview}
                </div>
              )}
              <button onClick={() => doDownload(lastReport.report_id)} style={s.btnGhost(G)} data-testid="cs-download-last">
                <Download size={11} style={{ display: "inline", marginRight: 4 }} /> Download PDF
              </button>
              <button onClick={() => doEmail(lastReport.report_id)} style={s.btnGhost("#7EC8A0")} data-testid="cs-email-last">
                <Send size={11} style={{ display: "inline", marginRight: 4 }} /> Email to Customer
              </button>
            </div>
          )}

          {preview && !lastReport && (
            <div style={s.card}>
              <div style={s.cardHead}>Preview · {preview.customer_name}</div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 14 }}>{preview.report_period_label}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
                <div style={s.kpi}><div style={s.kpiLabel}>Uptime</div><div style={s.kpiValue}>{preview.exec.uptime_pct}%</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Incidents</div><div style={s.kpiValue}>{preview.exec.incidents_resolved}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Hours Saved</div><div style={s.kpiValue}>{preview.exec.hours_saved}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>$ Saved</div><div style={s.kpiValue}>${preview.exec.dollars_saved}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Errors</div><div style={s.kpiValue}>{preview.sentinel.total_captured}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Auto-Healed</div><div style={s.kpiValue}>{preview.sentinel.auto_healed}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Voice Calls</div><div style={s.kpiValue}>{preview.ora.voice_calls}</div></div>
                <div style={s.kpi}><div style={s.kpiLabel}>Leads</div><div style={s.kpiValue}>{preview.ora.leads}</div></div>
              </div>
            </div>
          )}

          <div style={{ ...s.card, marginTop: 14 }}>
            <div style={{ ...s.cardHead, display: "flex", justifyContent: "space-between" }}>
              <span>Report History</span>
              <button onClick={loadHistory} style={{ ...s.btnGhost(G), padding: "3px 8px", marginRight: 0 }} data-testid="cs-refresh-history"><RefreshCw size={10} /></button>
            </div>
            <div style={{ maxHeight: 320, overflowY: "auto" }}>
              {history.map((r) => (
                <div key={r.report_id} style={{ padding: "10px 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }} data-testid={`cs-history-${r.report_id}`}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, color: "#fff", fontFamily: "'Cinzel', serif" }}>{r.report_id}</div>
                      <div style={{ fontSize: 10.5, color: "#888" }}>{r.customer_name} · {r.period_start} → {r.period_end}</div>
                      {r.emailed_to && <div style={{ fontSize: 10, color: "#7EC8A0", marginTop: 2 }}>✓ Emailed to {r.emailed_to}</div>}
                    </div>
                    <div style={{ whiteSpace: "nowrap" }}>
                      <button onClick={() => doDownload(r.report_id)} style={{ ...s.btnGhost(G), padding: "4px 10px", marginRight: 6 }}>PDF</button>
                      <button onClick={() => doEmail(r.report_id)} style={{ ...s.btnGhost("#7EC8A0"), padding: "4px 10px", marginRight: 0 }}>Send</button>
                    </div>
                  </div>
                </div>
              ))}
              {history.length === 0 && <div style={{ fontSize: 11, color: "#555", textAlign: "center", padding: 16 }}>No reports yet.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
