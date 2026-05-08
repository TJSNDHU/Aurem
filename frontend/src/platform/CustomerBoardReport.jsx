/**
 * CustomerBoardReport — Customer self-serve QBR PDF generator
 * ═══════════════════════════════════════════════════════════════════════════
 * Route: /my/board-report (inside CustomerPortal)
 *
 * Lets the paying customer generate, preview, download, and share their own
 * Business Review PDF built from verified AUREM telemetry (Site Monitor,
 * Sentinel, ORA). Useful for their own board meetings or investor updates.
 */
import React, { useState, useEffect, useCallback } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import { FileText, Download, Sparkles, Award, Shield, TrendingUp, Calendar, RefreshCw } from "lucide-react";
import { BACKEND_URL } from "../lib/api";

const API = BACKEND_URL;

export default function CustomerBoardReport() {
  const { apiJson, token } = useAuthFetch();
  const [reportType, setReportType] = useState("monthly");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [preview, setPreview] = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const G = "#D4AF37";

  const push = useCallback((m, t = "info") => { setToast({ m, t }); setTimeout(() => setToast(null), 3500); }, []);

  const loadHistory = useCallback(async () => {
    try {
      const d = await apiJson("/api/case-study/mine?limit=10");
      setHistory(d.reports || []);
    } catch { /* ignore */ }
  }, [apiJson]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const buildBody = () => ({
    report_type: reportType,
    ...(reportType === "custom" ? { period_start: customStart, period_end: customEnd } : {}),
  });

  const doPreview = async () => {
    setBusy(true);
    try {
      const d = await apiJson("/api/case-study/preview", { method: "POST", body: buildBody() });
      setPreview(d.preview);
      setLastReport(null);
    } catch (e) { push(`Preview failed: ${e.message}`, "error"); }
    setBusy(false);
  };

  const doGenerate = async () => {
    setBusy(true);
    try {
      const d = await apiJson("/api/case-study/generate", { method: "POST", body: buildBody() });
      setLastReport(d);
      setPreview(null);
      await loadHistory();
      push(`Board report ready · ${d.report_id}`, "success");
    } catch (e) { push(`Generation failed: ${e.message}`, "error"); }
    setBusy(false);
  };

  const doDownload = async (reportId) => {
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
    } catch (e) { push(`Download failed: ${e.message}`, "error"); }
  };

  return (
    <div className="p-6 md:p-10 min-h-screen" style={{ background: "#0A0A0F", color: "#E4DDD3" }} data-testid="customer-board-report">
      {toast && (
        <div style={{ position: "fixed", top: 20, right: 20, zIndex: 1000,
          background: toast.t === "error" ? "#1a0808" : toast.t === "success" ? "#081508" : "#10101a",
          border: `1px solid ${toast.t === "error" ? "#7a2020" : "#2a5a2a"}`,
          padding: "10px 16px", borderRadius: 5, fontSize: 12 }}>{toast.m}</div>
      )}

      <div className="max-w-5xl mx-auto">
        {/* Hero */}
        <div className="mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full mb-5 text-[10px] tracking-[3px]"
            style={{ background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.25)', color: G, textTransform: 'uppercase' }}>
            <Award size={11} /> BOARD-READY
          </div>
          <h1 className="text-3xl sm:text-4xl mb-3" style={{ fontFamily: 'Cinzel, serif', letterSpacing: 1 }}>
            Your <span style={{ color: G, fontStyle: 'italic' }}>Business Review</span>, Automated.
          </h1>
          <p className="text-sm max-w-2xl" style={{ color: "#aaa", lineHeight: 1.7 }}>
            Generate a professionally branded PDF for your board meetings in under 60 seconds.
            Built from verified AUREM telemetry — uptime, incidents, AI workforce activity, and
            a Claude-powered outlook for the next quarter.
          </p>
        </div>

        {/* Feature strip */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {[
            { icon: Shield, title: 'Verified Telemetry', body: 'Real data from Site Monitor, Sentinel, and ORA — no vanity metrics.' },
            { icon: TrendingUp, title: 'ROI Calculated', body: 'Hours saved, downtime avoided, dollars recovered — in black & white.' },
            { icon: Sparkles, title: 'AI Outlook', body: 'Claude 4.5 produces 3 predictive recommendations based on your own data.' },
          ].map((f, i) => (
            <div key={i} className="p-5 rounded-xl" style={{
              background: 'rgba(15,15,20,0.6)', border: '1px solid rgba(212,175,55,0.15)',
              backdropFilter: 'blur(14px)',
            }} data-testid={`cbr-feature-${i}`}>
              <f.icon size={18} style={{ color: G, marginBottom: 10 }} />
              <div className="text-sm font-bold mb-1" style={{ color: '#fff' }}>{f.title}</div>
              <div className="text-xs" style={{ color: '#9a9a9a', lineHeight: 1.55 }}>{f.body}</div>
            </div>
          ))}
        </div>

        {/* Generator */}
        <div className="rounded-xl p-6" style={{
          background: 'rgba(15,15,20,0.75)', border: '1px solid rgba(212,175,55,0.2)',
          backdropFilter: 'blur(18px)',
        }}>
          <div className="text-xs tracking-[3px] uppercase mb-5 font-bold" style={{ color: G }}>◆ Build Report</div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-5">
            {[
              { v: 'monthly', label: 'Monthly', hint: 'Last 30 days' },
              { v: 'quarterly', label: 'Quarterly', hint: 'Last 90 days' },
              { v: 'custom', label: 'Custom', hint: 'Pick date range' },
            ].map((opt) => (
              <button
                key={opt.v}
                onClick={() => setReportType(opt.v)}
                data-testid={`cbr-period-${opt.v}`}
                className="p-4 rounded-lg text-left transition-all"
                style={{
                  background: reportType === opt.v ? 'rgba(212,175,55,0.12)' : 'rgba(30,30,38,0.4)',
                  border: `1px solid ${reportType === opt.v ? G + '60' : 'rgba(255,255,255,0.05)'}`,
                  color: reportType === opt.v ? G : '#c4c4c4',
                  cursor: 'pointer',
                }}
              >
                <Calendar size={14} className="mb-2" />
                <div className="text-sm font-bold">{opt.label}</div>
                <div className="text-[10px] opacity-70 mt-1">{opt.hint}</div>
              </button>
            ))}
          </div>

          {reportType === 'custom' && (
            <div className="grid grid-cols-2 gap-3 mb-5">
              <input type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} data-testid="cbr-custom-start"
                className="px-3 py-2 rounded-md text-sm" style={{ background: '#0c0c0d', color: '#e4ddd3', border: '1px solid #222' }} />
              <input type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} data-testid="cbr-custom-end"
                className="px-3 py-2 rounded-md text-sm" style={{ background: '#0c0c0d', color: '#e4ddd3', border: '1px solid #222' }} />
            </div>
          )}

          <div className="flex gap-3 flex-wrap">
            <button onClick={doPreview} disabled={busy} data-testid="cbr-preview-btn"
              className="px-5 py-2.5 rounded-md text-xs font-bold tracking-wider uppercase transition-all hover:scale-[1.02]"
              style={{ background: 'transparent', border: `1px solid ${G}60`, color: G, cursor: 'pointer' }}>
              <Sparkles size={12} style={{ display: 'inline', marginRight: 6 }} />
              {busy ? 'Loading…' : 'Preview My Data'}
            </button>
            <button onClick={doGenerate} disabled={busy} data-testid="cbr-generate-btn"
              className="px-5 py-2.5 rounded-md text-xs font-bold tracking-wider uppercase transition-all hover:scale-[1.02]"
              style={{ background: G, color: '#0c0c0d', border: 'none', cursor: 'pointer', boxShadow: `0 4px 20px ${G}40` }}>
              <FileText size={12} style={{ display: 'inline', marginRight: 6 }} />
              {busy ? 'Building…' : 'Generate Board PDF'}
            </button>
          </div>
        </div>

        {/* Last / preview output */}
        {lastReport && (
          <div className="rounded-xl p-6 mt-6" style={{
            background: 'linear-gradient(135deg, rgba(212,175,55,0.08), rgba(15,15,20,0.8))',
            border: `1px solid ${G}50`, backdropFilter: 'blur(18px)',
          }} data-testid="cbr-last-report">
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs tracking-[3px] uppercase" style={{ color: G }}>◆ Report Ready</div>
                <div className="text-lg" style={{ fontFamily: 'Cinzel, serif', color: '#fff' }}>{lastReport.report_id}</div>
              </div>
              <button onClick={() => doDownload(lastReport.report_id)} data-testid="cbr-download-last"
                className="px-5 py-2.5 rounded-md text-xs font-bold uppercase tracking-wider"
                style={{ background: G, color: '#0c0c0d', border: 'none', cursor: 'pointer' }}>
                <Download size={12} style={{ display: 'inline', marginRight: 6 }} /> Download PDF
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { l: 'Uptime', v: `${lastReport.summary.uptime_pct}%` },
                { l: 'Hours Saved', v: lastReport.summary.hours_saved },
                { l: '$ Recovered', v: `$${lastReport.summary.dollars_saved}` },
                { l: 'Errors Caught', v: lastReport.summary.errors_captured },
              ].map((k) => (
                <div key={k.l} className="p-4 rounded-lg" style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(212,175,55,0.12)' }}>
                  <div className="text-[9px] tracking-[2.5px] uppercase font-bold mb-2" style={{ color: '#8a8a8a' }}>{k.l}</div>
                  <div style={{ fontFamily: 'Cinzel, serif', fontSize: 24, color: '#fff', lineHeight: 1 }}>{k.v}</div>
                </div>
              ))}
            </div>
            {lastReport.outlook_preview && (
              <div className="mt-4 p-4 rounded-md text-xs leading-relaxed" style={{
                background: 'rgba(212,175,55,0.05)', border: `1px solid ${G}20`, color: '#c9a227',
              }}>
                <strong>AI Outlook preview:</strong> {lastReport.outlook_preview}
              </div>
            )}
          </div>
        )}

        {preview && !lastReport && (
          <div className="rounded-xl p-6 mt-6" style={{
            background: 'rgba(15,15,20,0.7)', border: '1px solid rgba(212,175,55,0.18)',
            backdropFilter: 'blur(14px)',
          }} data-testid="cbr-preview-data">
            <div className="text-xs tracking-[3px] uppercase mb-4" style={{ color: G }}>◇ Preview · {preview.report_period_label}</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { l: 'Uptime', v: `${preview.exec.uptime_pct}%` },
                { l: 'Incidents', v: preview.exec.incidents_resolved },
                { l: 'Hours Saved', v: preview.exec.hours_saved },
                { l: '$ Saved', v: `$${preview.exec.dollars_saved}` },
                { l: 'Errors', v: preview.sentinel.total_captured },
                { l: 'Auto-Healed', v: preview.sentinel.auto_healed },
                { l: 'Voice Calls', v: preview.ora.voice_calls },
                { l: 'Leads', v: preview.ora.leads },
              ].map((k) => (
                <div key={k.l} className="p-3 rounded-lg" style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.04)' }}>
                  <div className="text-[9px] tracking-[2.5px] uppercase font-bold mb-1.5" style={{ color: '#7a7a7a' }}>{k.l}</div>
                  <div style={{ fontFamily: 'Cinzel, serif', fontSize: 22, color: '#fff', lineHeight: 1 }}>{k.v}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* History */}
        {history.length > 0 && (
          <div className="mt-10">
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs tracking-[3px] uppercase font-bold" style={{ color: G }}>◆ Your Past Reports</div>
              <button onClick={loadHistory} data-testid="cbr-refresh-history" style={{ background: 'transparent', color: G, border: `1px solid ${G}40`, padding: '4px 10px', borderRadius: 3, fontSize: 10, cursor: 'pointer' }}>
                <RefreshCw size={10} style={{ display: 'inline', marginRight: 4 }} /> Refresh
              </button>
            </div>
            <div className="space-y-2">
              {history.map((r) => (
                <div key={r.report_id} className="flex items-center justify-between p-3 rounded-lg" style={{
                  background: 'rgba(15,15,20,0.5)', border: '1px solid rgba(255,255,255,0.04)',
                }} data-testid={`cbr-history-${r.report_id}`}>
                  <div>
                    <div style={{ fontFamily: 'Cinzel, serif', fontSize: 13, color: '#fff' }}>{r.report_id}</div>
                    <div className="text-[10px]" style={{ color: '#888' }}>{r.period_start} → {r.period_end}</div>
                  </div>
                  <button onClick={() => doDownload(r.report_id)} data-testid={`cbr-download-${r.report_id}`}
                    style={{ background: 'transparent', color: G, border: `1px solid ${G}50`, padding: '5px 12px', borderRadius: 3, fontSize: 10.5, cursor: 'pointer' }}>
                    <Download size={10} style={{ display: 'inline', marginRight: 4 }} /> PDF
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
