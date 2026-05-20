/**
 * AdminSentinelClient — Trust-but-Verify Repair Queue
 * ═══════════════════════════════════════════════════════════════════
 * Route: /admin/sentinel-client
 * Access: super_admin only
 *
 * Shows:
 *  • Live errors feed (last 1h/24h) with classification + spike alerts
 *  • AI repair suggestions queue (pending/approved/rejected/modified)
 *  • Per-error "Analyze with Claude" button — opens structured suggestion
 *  • Approve / Reject / Modify review actions (no auto-deploy)
 */
import React, { useEffect, useState, useCallback } from "react";
import useAuthFetch from "../hooks/useAuthFetch";
import { AlertTriangle, Activity, Zap, CheckCircle2, XCircle, Edit3, RefreshCw, Brain } from "lucide-react";

const SEVERITY_COLOR = {
  P0: "#EF4444",
  P1: "#F97316",
  P2: "#C9A227",
  P3: "#7EC8A0",
};

const CLASSIFICATION_LABELS = {
  stale_preview_pod: "🛰 Stale Preview Pod",
  chunk_load_error: "📦 Chunk Load Error",
  auth_token_expired: "🔐 Auth Expired",
  rate_limited_429: "⏳ Rate Limit",
  network_failure: "🌐 Network Failure",
  backend_5xx: "🔥 Backend 5xx",
  client_4xx: "⚠ Client 4xx",
  js_exception: "💥 JS Exception",
  unhandled_rejection: "🧨 Unhandled Rejection",
  console_error: "📋 Console Error",
  resource_load_failure: "🖼 Resource 404",
  unknown: "❓ Unknown",
};

export default function AdminSentinelClient() {
  const { apiJson } = useAuthFetch();
  const [tab, setTab] = useState("overview"); // overview | errors | suggestions
  const [overview, setOverview] = useState(null);
  const [errors, setErrors] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState("");
  const [suggestionFilter, setSuggestionFilter] = useState("pending");
  const [analyzing, setAnalyzing] = useState(null);
  const [reviewing, setReviewing] = useState(null);
  const [toast, setToast] = useState(null);

  const push = useCallback((msg, type = "info") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadOverview = useCallback(async () => {
    try {
      const d = await apiJson("/api/admin/sentinel/overview");
      setOverview(d);
    } catch (e) {
      push(`Overview load failed: ${e.message}`, "error");
    }
  }, [apiJson, push]);

  const loadErrors = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filterType ? `?classification=${encodeURIComponent(filterType)}&limit=100` : "?limit=100";
      const d = await apiJson(`/api/admin/sentinel/errors${qs}`);
      setErrors(d.errors || []);
    } catch (e) {
      push(`Errors load failed: ${e.message}`, "error");
    }
    setLoading(false);
  }, [apiJson, filterType, push]);

  const loadSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiJson(`/api/admin/sentinel/suggestions?status=${suggestionFilter}&limit=100`);
      setSuggestions(d.suggestions || []);
    } catch (e) {
      push(`Suggestions load failed: ${e.message}`, "error");
    }
    setLoading(false);
  }, [apiJson, suggestionFilter, push]);

  useEffect(() => {
    loadOverview();
    const t = setInterval(loadOverview, 30000);
    return () => clearInterval(t);
  }, [loadOverview]);

  useEffect(() => {
    if (tab === "errors") loadErrors();
    if (tab === "suggestions") loadSuggestions();
  }, [tab, loadErrors, loadSuggestions]);

  const analyzeError = async (errorId) => {
    setAnalyzing(errorId);
    try {
      const d = await apiJson(`/api/admin/sentinel/analyze/${errorId}`, { method: "POST" });
      push(`AI diagnosis ${d.reused ? "reused" : "created"}: ${d.suggestion_id}`, "success");
      setTab("suggestions");
      setSuggestionFilter("pending");
      loadSuggestions();
    } catch (e) {
      push(`AI analyze failed: ${e.message}`, "error");
    }
    setAnalyzing(null);
  };

  const reviewSuggestion = async (suggestionId, action, note = "") => {
    setReviewing(suggestionId);
    try {
      await apiJson(`/api/admin/sentinel/suggestions/${suggestionId}/review`, {
        method: "POST",
        body: { action, note },
      });
      push(`Suggestion ${action}ed`, "success");
      loadSuggestions();
    } catch (e) {
      push(`Review failed: ${e.message}`, "error");
    }
    setReviewing(null);
  };

  // ═══ styles ═══
  const G = "#C9A227";
  const s = {
    root: { minHeight: "100vh", padding: "24px 28px", color: "#E4DDD3", fontFamily: "'Jost', sans-serif", background: "#050507" },
    title: { fontFamily: "'Cinzel', serif", fontSize: 22, color: G, letterSpacing: ".12em" },
    subtitle: { fontSize: 11, color: "#7a7a7a", letterSpacing: ".08em", textTransform: "uppercase", marginTop: 4 },
    tabBar: { display: "flex", gap: 4, marginTop: 24, marginBottom: 24, borderBottom: "1px solid rgba(201,162,39,0.15)" },
    tab: (a) => ({ padding: "10px 20px", fontSize: 12, cursor: "pointer", borderBottom: `2px solid ${a ? G : "transparent"}`, color: a ? G : "#7a7a7a", background: "transparent", border: "none", letterSpacing: ".06em", textTransform: "uppercase", fontWeight: 600 }),
    grid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginBottom: 24 },
    statCard: { background: "rgba(15,18,28,0.55)", border: `1px solid rgba(201,162,39,0.18)`, borderRadius: 10, padding: "16px 18px", backdropFilter: "blur(16px)" },
    statLabel: { fontSize: 10, color: "#7a7a7a", letterSpacing: ".12em", textTransform: "uppercase", fontWeight: 600, marginBottom: 6 },
    statVal: { fontSize: 28, fontWeight: 700, color: G, lineHeight: 1, fontFamily: "'Cinzel', serif" },
    card: { background: "rgba(15,18,28,0.5)", border: "1px solid rgba(201,162,39,0.15)", borderRadius: 8, padding: "14px 16px", marginBottom: 10 },
    badge: (c) => ({ fontSize: 9.5, padding: "2px 7px", borderRadius: 3, border: `1px solid ${c}40`, color: c, letterSpacing: ".08em", textTransform: "uppercase", fontWeight: 600 }),
    btnGold: { background: G, color: "#0c0c0d", border: "none", padding: "8px 14px", borderRadius: 4, cursor: "pointer", fontSize: 11, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase" },
    btnGhost: (c = "#7a7a7a") => ({ background: "transparent", border: `1px solid ${c}50`, color: c, padding: "6px 12px", borderRadius: 3, cursor: "pointer", fontSize: 10.5, letterSpacing: ".06em" }),
    select: { background: "#0c0c0d", color: "#e4ddd3", border: "1px solid #222", borderRadius: 3, padding: "6px 10px", fontSize: 11, fontFamily: "'Jost', sans-serif" },
  };

  return (
    <div style={s.root} data-testid="admin-sentinel-client">
      <div style={s.title}>⚡ Sentinel, Client Error Observability</div>
      <div style={s.subtitle}>Trust-but-verify repair queue · AI diagnoses, humans decide</div>

      {toast && (
        <div data-testid={`sentinel-toast-${toast.type}`} style={{ position: "fixed", top: 20, right: 20, zIndex: 1000, background: toast.type === "error" ? "#1a0808" : toast.type === "success" ? "#081508" : "#10101a", border: `1px solid ${toast.type === "error" ? "#7a2020" : "#2a5a2a"}`, color: "#e4ddd3", padding: "10px 16px", borderRadius: 5, fontSize: 12, boxShadow: "0 6px 24px rgba(0,0,0,.55)" }}>
          {toast.msg}
        </div>
      )}

      <div style={s.tabBar} data-testid="sentinel-tabs">
        <button data-testid="sentinel-tab-overview" style={s.tab(tab === "overview")} onClick={() => setTab("overview")}>
          <Activity size={12} style={{ display: "inline", marginRight: 6 }} /> Overview
        </button>
        <button data-testid="sentinel-tab-errors" style={s.tab(tab === "errors")} onClick={() => setTab("errors")}>
          <AlertTriangle size={12} style={{ display: "inline", marginRight: 6 }} /> Errors
        </button>
        <button data-testid="sentinel-tab-suggestions" style={s.tab(tab === "suggestions")} onClick={() => setTab("suggestions")}>
          <Brain size={12} style={{ display: "inline", marginRight: 6 }} /> AI Suggestions
        </button>
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {tab === "overview" && overview && (
        <>
          <div style={s.grid}>
            <div style={s.statCard} data-testid="stat-errors-1h">
              <div style={s.statLabel}>Errors · Last 1 Hr</div>
              <div style={s.statVal}>{overview.errors_1h}</div>
            </div>
            <div style={s.statCard} data-testid="stat-errors-24h">
              <div style={s.statLabel}>Errors · Last 24 Hr</div>
              <div style={s.statVal}>{overview.errors_24h}</div>
            </div>
            <div style={s.statCard} data-testid="stat-spikes">
              <div style={s.statLabel}>Active Spikes</div>
              <div style={{ ...s.statVal, color: overview.active_spikes?.length > 0 ? "#EF4444" : G }}>
                {overview.active_spikes?.length || 0}
              </div>
            </div>
            <div style={s.statCard} data-testid="stat-pending-suggestions">
              <div style={s.statLabel}>Pending AI Suggestions</div>
              <div style={s.statVal}>{overview.pending_ai_suggestions}</div>
            </div>
          </div>

          {overview.active_spikes?.length > 0 && (
            <div style={{ ...s.card, background: "rgba(239,68,68,0.08)", borderColor: "rgba(239,68,68,0.3)" }} data-testid="sentinel-spikes">
              <div style={{ fontSize: 12, color: "#EF4444", fontWeight: 700, marginBottom: 10, letterSpacing: ".08em", textTransform: "uppercase" }}>
                <Zap size={13} style={{ display: "inline", marginRight: 6 }} /> Active Error Spikes
              </div>
              {overview.active_spikes.map((spk) => (
                <div key={spk.signature} style={{ padding: "8px 0", borderBottom: "1px solid rgba(239,68,68,0.15)" }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                    <span style={s.badge("#EF4444")}>{CLASSIFICATION_LABELS[spk.classification] || spk.classification}</span>
                    <span style={{ fontSize: 11, color: "#e4ddd3" }}>{spk.count} events · {spk.unique_users} users</span>
                  </div>
                  <div style={{ fontSize: 11, color: "#888" }}>{spk.sample}</div>
                </div>
              ))}
            </div>
          )}

          <div style={{ fontSize: 11, color: G, letterSpacing: ".12em", textTransform: "uppercase", fontWeight: 700, marginTop: 24, marginBottom: 10 }}>Top Error Types (24h)</div>
          {(overview.top_types || []).map((t) => (
            <div key={t.type} style={s.card} data-testid={`top-type-${t.type}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={s.badge(G)}>{CLASSIFICATION_LABELS[t.type] || t.type}</span>
                  <span style={{ fontSize: 11, color: "#aaa", marginLeft: 10 }}>{t.unique_users} unique users</span>
                </div>
                <div style={{ fontSize: 16, fontWeight: 700, color: G }}>{t.count}</div>
              </div>
            </div>
          ))}
        </>
      )}

      {/* ═══ ERRORS TAB ═══ */}
      {tab === "errors" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center" }}>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              style={s.select}
              data-testid="sentinel-filter-type"
            >
              <option value="">All types</option>
              {Object.entries(CLASSIFICATION_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <button onClick={loadErrors} style={s.btnGhost(G)} data-testid="sentinel-refresh-errors">
              <RefreshCw size={11} style={{ display: "inline", marginRight: 4 }} /> Refresh
            </button>
            <span style={{ fontSize: 11, color: "#666" }}>{errors.length} shown</span>
          </div>

          {loading && <div style={{ fontSize: 11, color: "#666" }}>Loading…</div>}
          {errors.map((err) => (
            <div key={err.error_id} style={s.card} data-testid={`error-row-${err.error_id}`}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
                    <span style={s.badge(G)}>{CLASSIFICATION_LABELS[err.classification] || err.classification}</span>
                    {err.status_code ? <span style={s.badge("#7B9FD4")}>HTTP {err.status_code}</span> : null}
                    {err.auto_heal_key ? <span style={s.badge("#7EC8A0")}>AUTO-HEALABLE</span> : null}
                    {err.status === "analyzed" ? <span style={s.badge("#C47888")}>AI ANALYZED</span> : null}
                    <span style={{ fontSize: 10, color: "#555" }}>{new Date(err.ts).toLocaleString("en-CA")}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#e4ddd3", marginBottom: 4 }}>{err.message || "—"}</div>
                  {err.url && <div style={{ fontSize: 10.5, color: "#7B9FD4", wordBreak: "break-all" }}>{err.method || ""} {err.url}</div>}
                  {err.user_email && <div style={{ fontSize: 10, color: "#666", marginTop: 4 }}>👤 {err.user_email}</div>}
                </div>
                {err.ai_eligible && err.status !== "analyzed" && (
                  <button
                    onClick={() => analyzeError(err.error_id)}
                    disabled={analyzing === err.error_id}
                    style={{ ...s.btnGold, opacity: analyzing === err.error_id ? 0.5 : 1, whiteSpace: "nowrap" }}
                    data-testid={`analyze-${err.error_id}`}
                  >
                    {analyzing === err.error_id ? "Analyzing…" : <><Brain size={11} style={{ display: "inline", marginRight: 4 }} /> Analyze</>}
                  </button>
                )}
              </div>
            </div>
          ))}
          {!loading && errors.length === 0 && (
            <div style={{ fontSize: 12, color: "#555", padding: 24, textAlign: "center" }}>
              No errors in window. Healthy 🎉
            </div>
          )}
        </>
      )}

      {/* ═══ AI SUGGESTIONS TAB ═══ */}
      {tab === "suggestions" && (
        <>
          <div style={{ display: "flex", gap: 10, marginBottom: 14, alignItems: "center" }}>
            {["pending", "approved", "rejected", "modified"].map((f) => (
              <button
                key={f}
                onClick={() => setSuggestionFilter(f)}
                style={{ ...s.btnGhost(suggestionFilter === f ? G : "#555"), fontWeight: suggestionFilter === f ? 700 : 400 }}
                data-testid={`sug-filter-${f}`}
              >
                {f}
              </button>
            ))}
            <button onClick={loadSuggestions} style={s.btnGhost(G)} data-testid="sentinel-refresh-suggestions">
              <RefreshCw size={11} /> Refresh
            </button>
            <span style={{ fontSize: 11, color: "#666", marginLeft: "auto" }}>
              ℹ Human-in-the-loop only · AI never modifies code or deploys
            </span>
          </div>

          {loading && <div style={{ fontSize: 11, color: "#666" }}>Loading…</div>}
          {suggestions.map((sg) => (
            <div key={sg.suggestion_id} style={s.card} data-testid={`suggestion-${sg.suggestion_id}`}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
                <span style={s.badge(SEVERITY_COLOR[sg.severity] || G)}>{sg.severity}</span>
                <span style={s.badge(G)}>{CLASSIFICATION_LABELS[sg.error_snapshot?.classification] || sg.error_snapshot?.classification}</span>
                <span style={s.badge("#7EC8A0")}>Confidence: {Math.round((sg.confidence || 0) * 100)}%</span>
                {sg.requires_deploy && <span style={s.badge("#EF4444")}>Deploy Required</span>}
                <span style={{ fontSize: 10, color: "#555" }}>{new Date(sg.created_at).toLocaleString("en-CA")}</span>
              </div>
              <div style={{ fontSize: 11, color: "#7a7a7a", textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 700, marginBottom: 4 }}>Root Cause</div>
              <div style={{ fontSize: 12.5, color: "#e4ddd3", marginBottom: 10, lineHeight: 1.55 }}>{sg.root_cause}</div>

              <div style={{ fontSize: 11, color: "#7a7a7a", textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 700, marginBottom: 4 }}>Suggested Fix</div>
              <div style={{ fontSize: 12, color: "#C9A227", marginBottom: 10, lineHeight: 1.55, padding: "8px 12px", background: "rgba(201,162,39,0.06)", border: "1px solid rgba(201,162,39,0.15)", borderRadius: 4 }}>
                {sg.suggested_fix}
              </div>

              {sg.code_hint && (
                <>
                  <div style={{ fontSize: 11, color: "#7a7a7a", textTransform: "uppercase", letterSpacing: ".08em", fontWeight: 700, marginBottom: 4 }}>Code Hint</div>
                  <pre style={{ fontSize: 11, color: "#7EC8A0", background: "#0c0c0d", padding: "10px 12px", borderRadius: 4, overflow: "auto", margin: "0 0 10px 0", fontFamily: "'JetBrains Mono', monospace", whiteSpace: "pre-wrap" }}>{sg.code_hint}</pre>
                </>
              )}

              {sg.affected_files?.length > 0 && (
                <div style={{ fontSize: 10, color: "#666", marginBottom: 10 }}>
                  📁 {sg.affected_files.join(" · ")}
                </div>
              )}

              {sg.test_hint && (
                <div style={{ fontSize: 11, color: "#888", marginBottom: 10, fontStyle: "italic" }}>
                  Verify: {sg.test_hint}
                </div>
              )}

              {sg.status === "pending" && (
                <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                  <button
                    onClick={() => reviewSuggestion(sg.suggestion_id, "approve", "")}
                    disabled={reviewing === sg.suggestion_id}
                    style={{ ...s.btnGhost("#7EC8A0") }}
                    data-testid={`approve-${sg.suggestion_id}`}
                  >
                    <CheckCircle2 size={11} style={{ display: "inline", marginRight: 4 }} /> Approve
                  </button>
                  <button
                    onClick={() => reviewSuggestion(sg.suggestion_id, "reject", "")}
                    disabled={reviewing === sg.suggestion_id}
                    style={{ ...s.btnGhost("#EF4444") }}
                    data-testid={`reject-${sg.suggestion_id}`}
                  >
                    <XCircle size={11} style={{ display: "inline", marginRight: 4 }} /> Reject
                  </button>
                  <button
                    onClick={() => {
                      const note = prompt("Add a note for why this needs modification:");
                      if (note !== null) reviewSuggestion(sg.suggestion_id, "modify", note);
                    }}
                    disabled={reviewing === sg.suggestion_id}
                    style={{ ...s.btnGhost("#7B9FD4") }}
                    data-testid={`modify-${sg.suggestion_id}`}
                  >
                    <Edit3 size={11} style={{ display: "inline", marginRight: 4 }} /> Modify
                  </button>
                </div>
              )}

              {sg.status !== "pending" && (
                <div style={{ fontSize: 10.5, color: "#555", marginTop: 10 }}>
                  {sg.status} by {sg.reviewed_by} · {sg.reviewed_at ? new Date(sg.reviewed_at).toLocaleString("en-CA") : ""}
                  {sg.review_note ? ` — ${sg.review_note}` : ""}
                </div>
              )}
            </div>
          ))}
          {!loading && suggestions.length === 0 && (
            <div style={{ fontSize: 12, color: "#555", padding: 24, textAlign: "center" }}>
              No {suggestionFilter} suggestions.
            </div>
          )}
        </>
      )}
    </div>
  );
}
