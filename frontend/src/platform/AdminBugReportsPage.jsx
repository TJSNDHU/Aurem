/**
 * AdminBugReportsPage.jsx — iter D-60
 *
 * Inbox for BugCatch reports. Shows list with severity / status filter,
 * detail view with screenshot, AI root cause, console logs, network
 * calls, and status flipper.
 */
import React, { useEffect, useState, useCallback } from "react";
import { Bug, RefreshCw, Filter, CheckCircle2, AlertTriangle,
         X, Search } from "lucide-react";

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

const C = {
  ink: "#F0EDE8", dim: "#a1958a", gold: "#E8C86A",
  amber: "#FF8C35", red: "#FF6060", green: "#4ade80",
  panel: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.10)",
};
const mono = "'JetBrains Mono', monospace";

const SEV_COLOR = { low: C.green, med: C.gold, high: C.red };
const STATUS_TINT = {
  open:          { c: C.red,   label: "open" },
  investigating: { c: C.gold,  label: "investigating" },
  resolved:      { c: C.green, label: "resolved" },
  wont_fix:      { c: C.dim,   label: "won't fix" },
};


export default function AdminBugReportsPage() {
  const [items, setItems]     = useState([]);
  const [stats, setStats]     = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [filter, setFilter]   = useState("");
  const [active, setActive]   = useState(null);   // full report

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const qs = filter ? `?status=${filter}&limit=100` : "?limit=100";
      const [r, s] = await Promise.all([
        fetch(`${API}/api/admin/bug-reports${qs}`,
                { headers: adminHeaders() }),
        fetch(`${API}/api/admin/bug-reports/stats`,
                { headers: adminHeaders() }),
      ]);
      const jr = await r.json();
      const js = await s.json();
      if (!r.ok) throw new Error(jr.detail || "load_failed");
      setItems(jr.items || []);
      setStats(js.stats || {});
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  async function openDetail(reportId) {
    try {
      const r = await fetch(`${API}/api/admin/bug-reports/${reportId}`,
                              { headers: adminHeaders() });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "load_detail_failed");
      setActive(j.report);
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  async function setStatus(reportId, status) {
    try {
      await fetch(`${API}/api/admin/bug-reports/${reportId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...adminHeaders() },
        body: JSON.stringify({ status }),
      });
      if (active && active.report_id === reportId) {
        setActive({ ...active, status });
      }
      load();
    } catch (e) {
      setError(String(e.message || e));
    }
  }

  return (
    <div data-testid="admin-bug-reports-page"
         style={{ padding: "24px 28px", maxWidth: 1300, margin: "0 auto",
                  color: C.ink }}>

      <div style={{ display: "flex", alignItems: "center", gap: 12,
                    marginBottom: 18 }}>
        <Bug size={18} style={{ color: C.amber }} />
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: 22,
                     color: C.gold, margin: 0 }}>
          BugCatch · Reports
        </h1>
        <span style={{ marginLeft: "auto", fontSize: 11, fontFamily: mono,
                       display: "flex", gap: 10 }}>
          <span style={{ color: C.red }}>● {stats.open || 0} open</span>
          <span style={{ color: C.gold }}>
            ● {stats.investigating || 0} investigating
          </span>
          <span style={{ color: C.green }}>
            ● {stats.resolved || 0} resolved
          </span>
        </span>
        <button onClick={load} disabled={loading}
                data-testid="bug-reports-refresh"
                style={{ background: C.panel, border: `1px solid ${C.border}`,
                         color: C.dim, padding: "6px 12px",
                         borderRadius: 4, fontSize: 11,
                         cursor: loading ? "wait" : "pointer",
                         display: "inline-flex", alignItems: "center", gap: 5 }}>
          <RefreshCw size={12}
                     className={loading ? "aurem-anim-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Filter chips */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12,
                    fontSize: 11, fontFamily: mono }}>
        <Filter size={12} style={{ color: C.dim, alignSelf: "center" }} />
        {["", "open", "investigating", "resolved", "wont_fix"].map(s => (
          <button key={s || "all"} onClick={() => setFilter(s)}
                  data-testid={`bug-filter-${s || "all"}`}
                  style={{ padding: "4px 10px",
                           background: filter === s
                             ? "rgba(255,140,53,0.18)"
                             : "rgba(255,255,255,0.02)",
                           border: `1px solid ${filter === s
                             ? C.amber : C.border}`,
                           color: filter === s ? C.amber : C.dim,
                           borderRadius: 4, cursor: "pointer" }}>
            {s || "all"}
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: 10, marginBottom: 12, color: C.red,
                      background: "rgba(255,96,96,0.08)",
                      border: "1px solid rgba(255,96,96,0.30)",
                      borderRadius: 4, fontSize: 12 }}>
          {error}
        </div>
      )}

      {items.length === 0 && !loading && (
        <div style={{ padding: 24, color: C.dim, fontSize: 12,
                      fontFamily: mono,
                      border: `1px dashed ${C.border}`,
                      borderRadius: 5 }}>
          No reports yet. Click the orange 🐛 bug button bottom-right
          on any admin page to file one.
        </div>
      )}

      {items.map(it => (
        <div key={it.report_id}
             data-testid={`bug-row-${it.report_id}`}
             onClick={() => openDetail(it.report_id)}
             style={{ padding: 11, marginBottom: 7,
                      background: C.panel,
                      border: `1px solid ${C.border}`,
                      borderRadius: 5, cursor: "pointer",
                      display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%",
                          background: SEV_COLOR[it.severity] || C.dim }} />
          <strong style={{ color: C.ink, fontSize: 12,
                            fontFamily: mono, minWidth: 110 }}>
            {it.report_id}
          </strong>
          <span style={{ color: C.dim, fontSize: 11,
                          fontFamily: mono, minWidth: 200 }}>
            {it.url || "(no url)"}
          </span>
          <span style={{ color: C.ink, fontSize: 12, flex: 1,
                          overflow: "hidden", textOverflow: "ellipsis",
                          whiteSpace: "nowrap" }}>
            {it.description || "(no description)"}
          </span>
          <span style={{ color: STATUS_TINT[it.status]?.c || C.dim,
                          fontSize: 11, fontFamily: mono }}>
            {STATUS_TINT[it.status]?.label || it.status}
          </span>
          <span style={{ color: C.dim, fontSize: 10, fontFamily: mono }}>
            {it.ts?.slice(0, 16)}
          </span>
        </div>
      ))}

      {/* Detail drawer */}
      {active && (
        <div data-testid="bug-detail-drawer"
             style={{ position: "fixed", inset: 0,
                      background: "rgba(0,0,0,0.78)", zIndex: 9100,
                      display: "flex", alignItems: "flex-start",
                      justifyContent: "center", padding: 22,
                      overflow: "auto" }}>
          <div style={{ width: "100%", maxWidth: 1100,
                        background: "#13110d",
                        border: `1px solid ${C.border}`,
                        borderRadius: 8, padding: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10,
                           marginBottom: 12 }}>
              <Bug size={16} style={{ color: C.amber }} />
              <strong style={{ color: C.gold, fontSize: 14 }}>
                {active.report_id} · {active.severity?.toUpperCase()}
              </strong>
              <span style={{ color: C.dim, fontSize: 11,
                              fontFamily: mono }}>
                {active.ts?.slice(0, 19)} · {active.submitted_by}
              </span>
              <button onClick={() => setActive(null)}
                      data-testid="bug-detail-close"
                      style={{ marginLeft: "auto", background: "transparent",
                               border: "none", color: C.dim,
                               cursor: "pointer" }}>
                <X size={16} />
              </button>
            </div>

            <div style={{ marginBottom: 12, fontSize: 12,
                           color: C.ink, fontFamily: mono }}>
              <strong style={{ color: C.gold }}>URL:</strong>{" "}
              {active.url || "(none)"}
              <br />
              <strong style={{ color: C.gold }}>viewport:</strong>{" "}
              {active.viewport?.w}×{active.viewport?.h}
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong style={{ color: C.gold, fontSize: 12 }}>
                Description:
              </strong>
              <div style={{ marginTop: 4, padding: 10,
                             background: "rgba(0,0,0,0.30)",
                             border: `1px solid ${C.border}`,
                             borderRadius: 4, fontSize: 12,
                             color: C.ink, whiteSpace: "pre-wrap" }}>
                {active.description || "(none)"}
              </div>
            </div>

            {active.ai_root_cause && (
              <div style={{ marginBottom: 12, padding: 10,
                             background: "rgba(232,200,106,0.08)",
                             border: "1px solid rgba(232,200,106,0.35)",
                             borderRadius: 4 }}>
                <div style={{ color: C.gold, fontSize: 12, fontWeight: 500,
                               marginBottom: 4 }}>
                  AI root cause · {active.ai_model}
                </div>
                <div style={{ color: C.ink, fontSize: 12 }}>
                  {active.ai_root_cause}
                </div>
              </div>
            )}

            {active.screenshot_b64 && (
              <div style={{ marginBottom: 12 }}>
                <strong style={{ color: C.gold, fontSize: 12 }}>
                  Screenshot:
                </strong>
                <div style={{ marginTop: 6 }}>
                  <img src={active.screenshot_b64}
                       data-testid="bug-detail-screenshot"
                       alt="screenshot"
                       style={{ maxWidth: "100%",
                                 border: `1px solid ${C.border}`,
                                 borderRadius: 4 }} />
                </div>
              </div>
            )}

            <details style={{ marginBottom: 10 }}>
              <summary style={{ cursor: "pointer", color: C.gold,
                                 fontSize: 12 }}>
                Console logs ({active.console_logs?.length || 0})
              </summary>
              <div style={{ marginTop: 6, maxHeight: 240, overflow: "auto",
                             padding: 8, background: "rgba(0,0,0,0.30)",
                             border: `1px solid ${C.border}`,
                             borderRadius: 4, fontFamily: mono,
                             fontSize: 11 }}>
                {(active.console_logs || []).map((l, i) => (
                  <div key={i}
                       style={{ color: l.level === "error" ? C.red
                                : l.level === "warn" ? C.gold : C.dim,
                                marginBottom: 2 }}>
                    [{l.level}] {l.msg}
                  </div>
                ))}
              </div>
            </details>

            <details style={{ marginBottom: 14 }}>
              <summary style={{ cursor: "pointer", color: C.gold,
                                 fontSize: 12 }}>
                Network calls ({active.network_calls?.length || 0})
              </summary>
              <div style={{ marginTop: 6, maxHeight: 240, overflow: "auto",
                             padding: 8, background: "rgba(0,0,0,0.30)",
                             border: `1px solid ${C.border}`,
                             borderRadius: 4, fontFamily: mono,
                             fontSize: 11 }}>
                {(active.network_calls || []).map((n, i) => (
                  <div key={i}
                       style={{ color: n.status >= 400 ? C.red
                                : n.status >= 300 ? C.gold : C.dim,
                                marginBottom: 2 }}>
                    {n.method} {n.url} → {n.status} ({n.latency_ms}ms)
                  </div>
                ))}
              </div>
            </details>

            {/* Status flipper */}
            <div style={{ display: "flex", gap: 8 }}>
              {Object.keys(STATUS_TINT).map(s => (
                <button key={s}
                        onClick={() => setStatus(active.report_id, s)}
                        data-testid={`bug-set-status-${s}`}
                        style={{ padding: "6px 14px",
                                 background: active.status === s
                                   ? "rgba(255,140,53,0.18)"
                                   : "rgba(255,255,255,0.02)",
                                 border: `1px solid ${active.status === s
                                   ? C.amber : C.border}`,
                                 color: active.status === s ? C.amber : C.dim,
                                 borderRadius: 4, fontSize: 11,
                                 cursor: "pointer" }}>
                  {STATUS_TINT[s].label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
