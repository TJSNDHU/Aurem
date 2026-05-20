/* AdminStemFix.jsx — Phase 2 Root-Level Refactor Queue (iter 267)
 * ================================================================
 * Unlike the Auto-Fixer (patches), this dashboard shows CLAUDE-GENERATED
 * STRUCTURAL REFACTORS of the offending source functions. Admin reviews
 * the diff, sees the regression_risks + qa_steps Claude produced, and
 * approves to write the refactor back to the source file.
 *
 *   GET  /api/admin/stem-fix/pending
 *   POST /api/admin/stem-fix/{id}/approve
 *   POST /api/admin/stem-fix/{id}/reject
 *   POST /api/admin/stem-fix/generate  (triggered from Root Command)
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  Loader2, CheckCircle, XCircle, Clock, AlertTriangle,
  FileCode, Zap, RefreshCw, Shield, Code,
} from "lucide-react";
import MissionControlRibbon from "./MissionControlRibbon";

const API = process.env.REACT_APP_BACKEND_URL || "";

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

const SEVERITY_COLORS = {
  critical: "#EF4444",
  high:     "#F59E0B",
  medium:   "#3b82f6",
  low:      "#22C55E",
};

const STATUS_META = {
  pending:  { color: "#F59E0B", icon: Clock,         label: "Pending Review" },
  approved: { color: "#3b82f6", icon: CheckCircle,   label: "Applied (no QA)" },
  verified: { color: "#22C55E", icon: CheckCircle,   label: "✓ Verified by QA" },
  rejected: { color: "#6B7280", icon: XCircle,       label: "Rejected" },
  failed:   { color: "#DC2626", icon: AlertTriangle, label: "Failed (rolled back)" },
  regression_failed: { color: "#DC2626", icon: AlertTriangle, label: "QA Regression — Rolled Back" },
};

export default function AdminStemFix() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [err, setErr] = useState(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const res = await fetch(`${API}/api/admin/stem-fix/pending`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      setItems(Array.isArray(j.items) ? j.items : []);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, [load]);

  const act = async (fixId, verb) => {
    setBusyId(fixId);
    try {
      const res = await fetch(`${API}/api/admin/stem-fix/${fixId}/${verb}`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || body.ok === false) {
        alert(`Stem-Fix ${verb} failed: ${body.reason || body.detail || res.status}`);
      }
      await load();
    } catch (e) {
      alert(`Network error: ${e}`);
    } finally {
      setBusyId(null);
    }
  };

  if (loading && items.length === 0) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center" data-testid="stem-fix-loading">
        <Loader2 className="size-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100" data-testid="stem-fix-page">
      <MissionControlRibbon />
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold mb-1">Stem-Fix Queue</h1>
            <p className="text-gray-400 text-sm">
              Structural refactors, the source gets healed, not patched.
            </p>
          </div>
          <button
            onClick={load}
            data-testid="stem-fix-refresh"
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded text-sm hover:bg-gray-700"
          >
            <RefreshCw className="size-4" /> Refresh
          </button>
        </div>

        {err && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
            {err}
          </div>
        )}

        {items.length === 0 ? (
          <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-10 text-center" data-testid="stem-fix-empty">
            <Shield className="size-12 mx-auto text-green-500 mb-3" />
            <div className="text-lg font-semibold text-gray-200">No stem-fixes yet</div>
            <p className="text-sm text-gray-500 mt-2">
              Generate one from the <strong>Root Command</strong> page by clicking
              "Generate Stem-Fix" on any error card.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((it) => {
              const meta = STATUS_META[it.status] || STATUS_META.pending;
              const StatusIcon = meta.icon;
              const claude = it.claude_response || {};
              const sev = claude.severity || "medium";
              const isOpen = expanded === it.id;
              const isPending = it.status === "pending";

              return (
                <div
                  key={it.id}
                  data-testid={`stem-fix-row-${it.id}`}
                  className="rounded-lg border border-gray-800 bg-gray-900/60"
                >
                  <div
                    className="p-4 cursor-pointer hover:bg-gray-900/80"
                    onClick={() => setExpanded(isOpen ? null : it.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div
                        className="size-2 rounded-full mt-2 flex-shrink-0"
                        style={{ backgroundColor: SEVERITY_COLORS[sev] }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <StatusIcon className="size-4" style={{ color: meta.color }} />
                          <span className="text-xs font-semibold" style={{ color: meta.color }}>
                            {meta.label}
                          </span>
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded uppercase font-bold"
                            style={{
                              color: SEVERITY_COLORS[sev],
                              backgroundColor: `${SEVERITY_COLORS[sev]}20`,
                            }}
                          >
                            {sev}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-sm">
                          <Code className="size-4 text-gray-500" />
                          <span className="font-mono text-gray-300">{it.target_function}()</span>
                          <span className="text-gray-500 font-mono text-xs">
                            {it.target_file?.split("/").slice(-3).join("/")}:{it.start_line}-{it.end_line}
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-gray-400 line-clamp-2">
                          {claude.root_cause || it.error_message || "—"}
                        </div>
                      </div>
                      {isPending && (
                        <div className="flex gap-2 flex-shrink-0">
                          <button
                            disabled={busyId === it.id}
                            onClick={(e) => { e.stopPropagation(); act(it.id, "approve"); }}
                            data-testid={`stem-fix-approve-${it.id}`}
                            className="px-3 py-1 bg-green-800 text-green-100 rounded text-xs hover:bg-green-700 disabled:opacity-50"
                          >
                            Approve & Apply
                          </button>
                          <button
                            disabled={busyId === it.id}
                            onClick={(e) => { e.stopPropagation(); act(it.id, "reject"); }}
                            data-testid={`stem-fix-reject-${it.id}`}
                            className="px-3 py-1 bg-gray-800 text-gray-300 rounded text-xs hover:bg-gray-700 disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="border-t border-gray-800 p-4 bg-gray-950" data-testid={`stem-fix-detail-${it.id}`}>
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                        <div>
                          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Refactor Strategy</div>
                          <p className="text-sm text-gray-300">{claude.refactor_strategy || "—"}</p>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Regression Risks</div>
                          {(claude.regression_risks || []).length > 0 ? (
                            <ul className="text-xs text-amber-200 space-y-1">
                              {claude.regression_risks.map((r, i) => <li key={i}>• {r}</li>)}
                            </ul>
                          ) : (
                            <p className="text-xs text-gray-600">None flagged</p>
                          )}
                        </div>
                      </div>

                      {claude.qa_steps?.length > 0 && (
                        <div className="mb-4">
                          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">QA Verification Steps</div>
                          <ul className="text-xs text-blue-300 font-mono space-y-1">
                            {claude.qa_steps.map((s, i) => <li key={i}>$ {s}</li>)}
                          </ul>
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <div className="text-xs text-red-300 uppercase tracking-wide mb-2 flex items-center gap-1">
                            <XCircle className="size-3" /> Original Source
                          </div>
                          <pre className="text-[11px] bg-red-950/20 border border-red-900/50 text-red-100 p-3 rounded max-h-64 overflow-auto font-mono">
                            {it.original_source || "(empty)"}
                          </pre>
                        </div>
                        <div>
                          <div className="text-xs text-green-300 uppercase tracking-wide mb-2 flex items-center gap-1">
                            <CheckCircle className="size-3" /> Proposed Refactor
                          </div>
                          <pre className="text-[11px] bg-green-950/20 border border-green-900/50 text-green-100 p-3 rounded max-h-64 overflow-auto font-mono">
                            {claude.new_function_source || "(empty)"}
                          </pre>
                        </div>
                      </div>

                      {it.status === "failed" && it.failure_reason && (
                        <div className="mt-4 p-3 bg-red-900/30 border border-red-700 rounded text-xs text-red-300">
                          <strong>Rollback reason:</strong> {it.failure_reason}
                        </div>
                      )}

                      {/* QA Result Panel — Phase 3 self-verification output */}
                      {it.qa_result && (
                        <div className="mt-4 p-3 bg-gray-900 border border-gray-800 rounded" data-testid={`stem-fix-qa-${it.id}`}>
                          <div className="flex items-center justify-between mb-2">
                            <div className="text-xs uppercase tracking-wide text-gray-400 flex items-center gap-1">
                              <Zap className="size-3" /> QA Self-Verification
                            </div>
                            <div className="text-xs">
                              <span className="text-green-400">{it.qa_result.passed}✓</span>
                              <span className="text-gray-500 mx-1">/</span>
                              <span className="text-red-400">{it.qa_result.failed}✗</span>
                              <span className="text-gray-500 mx-1">/</span>
                              <span className="text-gray-400">{it.qa_result.skipped || 0} skipped</span>
                            </div>
                          </div>
                          <div className="space-y-1 max-h-40 overflow-auto">
                            {(it.qa_result.results || []).map((r, i) => (
                              <div key={i} className="text-[11px] font-mono flex items-start gap-2">
                                {r.skipped ? (
                                  <span className="text-gray-500 flex-shrink-0">⊘</span>
                                ) : r.ok ? (
                                  <span className="text-green-400 flex-shrink-0">✓{r.status_code ? ` ${r.status_code}` : ""}</span>
                                ) : (
                                  <span className="text-red-400 flex-shrink-0">✗{r.status_code ? ` ${r.status_code}` : ""}</span>
                                )}
                                <span className="text-gray-400 truncate">{r.cmd}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
