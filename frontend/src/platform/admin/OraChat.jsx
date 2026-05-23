/**
 * OraChat.jsx — Single autonomous chat with ORA (iter 322fi).
 *
 * Founder mandate: ONE chat. No tab switching. No manual tool picking.
 *   - ORA reads/greps/curls autonomously (tier 1 — silent, fast)
 *   - For mutating actions (tier 2), shows inline [Approve][Reject] card
 *   - For destructive (tier 3), red banner card + same buttons
 *
 * Backend: /api/ora/agent/run + /api/ora/agent/{approve,reject}
 *
 * Persistence: server-side per session_id; we also cache the session_id
 * locally so refresh keeps the thread.
 */
import React, { useEffect, useRef, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Crown, Send, Loader2, Trash2, Copy, Check,
  Wrench, AlertTriangle, ShieldAlert, X, Wand2, Eye,
  ChevronRight, Sparkles, Plus,
} from "lucide-react";
import {
  SmartToolResult, PreviewPane, StepTracker, PlanPreview,
  ErrorContext, extractPlanSteps,
} from "./OraChatViews";

const API = process.env.REACT_APP_BACKEND_URL || "";
const SESSION_KEY = "aurem.ora-agent.session.v1";

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

const TIER_STYLES = {
  tier1_auto:      { color: GREEN,  label: "AUTO",      bg: "rgba(103,232,160,0.10)" },
  tier2_approve:   { color: AMBER,  label: "APPROVE",   bg: "rgba(255,179,107,0.10)" },
  tier3_high_risk: { color: RED,    label: "HIGH RISK", bg: "rgba(255,118,118,0.12)" },
};

function authHeaders() {
  const t =
    sessionStorage.getItem("platform_token") ||
    localStorage.getItem("platform_token") ||
    localStorage.getItem("aurem_admin_token") ||
    sessionStorage.getItem("aurem_admin_token") ||
    localStorage.getItem("token") ||
    "";
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function safeJson(r) {
  let text = "";
  try { text = await r.text(); } catch { /* network */ }
  try {
    const j = text ? JSON.parse(text) : {};
    if (typeof j === "object" && j !== null) {
      if (!("ok" in j)) j.ok = r.ok;
      j._http_status = r.status;
      return j;
    }
    return { ok: r.ok, _http_status: r.status, value: j };
  } catch {
    return {
      ok: false,
      _http_status: r.status,
      error: `HTTP ${r.status} ${r.statusText || ""}`.trim(),
      preview: (text || "").slice(0, 220),
    };
  }
}

export default function OraChat() {
  const navigate = useNavigate();
  const [sessionId] = useState(() => {
    try {
      let id = localStorage.getItem(SESSION_KEY);
      if (!id) {
        id = `ora-${Date.now().toString(36)}`;
        localStorage.setItem(SESSION_KEY, id);
      }
      return id;
    } catch { return `ora-${Date.now().toString(36)}`; }
  });
  const [history, setHistory] = useState([]);   // {role, content, ts, tool_calls?, ...}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyStartedAt, setBusyStartedAt] = useState(0); // wall-clock ms when send() flipped busy=true
  const [busyElapsedS, setBusyElapsedS] = useState(0);   // seconds ticker, updated by interval
  const [busyTools, setBusyTools] = useState([]);        // live tool_calls_so_far during async job (iter 323l)
  const [pending, setPending] = useState(null); // current action_required
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [error, setError] = useState(null);

  // iter 327c — multi-upload state. attachments[] holds metadata
  // for files the user picked but hasn't sent yet. They're posted
  // alongside the next message via attachment_ids in the run-async
  // body. ORA's backend resolves them and pastes preview text into
  // the user message so the LLM brain reads the upload.
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading]     = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChosen = async (e) => {
    const f = e.target.files && e.target.files[0];
    if (e.target) e.target.value = "";   // allow re-picking same file
    if (!f) return;
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("session_id", sessionId);
      const r = await fetch(`${API}/api/ora/agent/attach`, {
        method: "POST",
        headers: { ...authHeaders() },
        body: fd,
      });
      const j = await safeJson(r);
      if (!j || !j.ok || !j.attachment) {
        throw new Error((j && (j.error || j.detail)) || "upload failed");
      }
      setAttachments((arr) => [...arr, j.attachment]);
    } catch (err) {
      setError(`Upload failed: ${err.message || err}`);
    } finally {
      setUploading(false);
    }
  };

  const removeAttachment = (id) => {
    setAttachments((arr) => arr.filter((a) => a.attachment_id !== id));
  };

  // iter 326uu — derived: latest tool_result for the right-side PreviewPane.
  const latestToolResult = useMemo(() => {
    for (let i = history.length - 1; i >= 0; i--) {
      const m = history[i];
      if (m && m.role === "tool_result") {
        let parsed = m.result;
        if (!parsed && m.content) {
          if (typeof m.content === "object") parsed = m.content;
          else { try { parsed = JSON.parse(m.content); }
                 catch { parsed = { raw: String(m.content) }; } }
        }
        return { tool: m.tool, result: parsed || { ok: true } };
      }
    }
    return null;
  }, [history]);

  // iter 326uu — derived: parse the FIRST assistant message for a numbered/
  // bulleted plan so we can render a checklist above the chat.
  const planSteps = useMemo(() => {
    for (const m of history) {
      if (m && m.role === "assistant" && m.content) {
        const steps = extractPlanSteps(m.content);
        if (steps.length >= 2) return steps;
      }
    }
    return [];
  }, [history]);

  // iter 326uu — derived: completed plan steps from busyTools count
  // (used to strike-through finished items in the PlanPreview).
  const planDoneSet = useMemo(() => {
    const done = new Set();
    if (planSteps.length === 0) return done;
    // Use the count of tool_result messages as a coarse "step n done" hint.
    let n = 0;
    for (const m of history) if (m.role === "tool_result") n++;
    for (let i = 0; i < Math.min(n, planSteps.length); i++) done.add(i);
    return done;
  }, [history, planSteps]);

  const scrollRef = useRef(null);
  // FIX #6 (audit) — track the active copy-feedback timer so unmount or a
  // rapid second copy cancels the pending setCopiedIdx(null) call.
  // Without this, an unmount within 1.5s of a copy fired setState on a
  // dead component (React dev warning, no real leak but ugly).
  const copyTimerRef = useRef(null);

  // Cleanup pending copy timer on unmount
  useEffect(() => {
    return () => {
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
        copyTimerRef.current = null;
      }
    };
  }, []);

  // Load server-side history once at mount
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const r = await fetch(`${API}/api/ora/agent/history/${sessionId}`,
                              { headers: authHeaders() });
        const j = await safeJson(r);
        if (!cancel && j.ok && Array.isArray(j.messages)) {
          // Convert server format → flat UI rows
          const ui = [];
          for (const m of j.messages) {
            if (m.role === "user") {
              ui.push({ role: "user", content: m.content || "", ts: 0 });
            } else if (m.role === "assistant") {
              if (m.content) ui.push({ role: "assistant", content: m.content, ts: 0 });
              for (const tc of (m.tool_calls || [])) {
                ui.push({ role: "tool_call", tool: tc.function?.name,
                           args: _safeArgs(tc.function?.arguments) });
              }
            } else if (m.role === "tool") {
              ui.push({ role: "tool_result", tool: m.name,
                         content: m.content || "", ts: 0 });
            }
          }
          setHistory(ui);
        }
      } catch { /* soft */ }
    })();
    return () => { cancel = true; };
  }, [sessionId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history, busy, pending]);

  // ── Elapsed-time ticker for the WORKING… indicator (iter 323k) ─────
  // ORA's Groq tool-calling loop legitimately takes 30-60 s on complex
  // queries. Without a live counter the UI looks frozen and the founder
  // closes the tab thinking it crashed. Tick every second while busy so
  // the user sees "ORA is working… 12s" and knows the system is alive.
  useEffect(() => {
    if (!busy) { setBusyElapsedS(0); return undefined; }
    const start = busyStartedAt || Date.now();
    setBusyElapsedS(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    const id = setInterval(() => {
      setBusyElapsedS(Math.max(0, Math.floor((Date.now() - start) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [busy, busyStartedAt]);

  const copy = async (text, idx) => {
    try {
      if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text);
      else {
        const ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand("copy"); ta.remove();
      }
      setCopiedIdx(idx);
      // Cancel any prior pending reset so rapid second copies don't race
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => {
        setCopiedIdx((v) => (v === idx ? null : v));
        copyTimerRef.current = null;
      }, 1500);
    } catch { /* clipboard blocked */ }
  };

  // ── Async polling helper — bypasses Cloudflare's 100s timeout ─────
  // Production aurem.live sits behind Cloudflare Free which kills any
  // single HTTP request taking >100 s with a 524. ORA's tool-calling
  // loop against the local Ollama daemon routinely exceeds that on
  // complex queries. Instead we:
  //   1. POST /run-async         → returns job_id in <100 ms
  //   2. GET  /status/{job_id}   → poll every 2.5 s; CF sees only
  //                                short, healthy requests
  // The backend worker (services/ora_agent_jobs.py) executes the real
  // ora_agent.run_turn() in the background — survives pod restarts
  // because the job is persisted in Mongo.
  //
  // If /run-async doesn't exist on the deployed backend (e.g. running
  // a stale build), we transparently fall back to the legacy /run.
  // iter 323aa — tightened to 1200 ms (was 2500 ms). At 1.2s the perceived
  // latency floor for a 5s real backend response drops from ~3.75s to
  // ~2.0s. Job-status endpoint is a single Mongo lookup, very cheap.
  const POLL_INTERVAL_MS = 1200;
  const POLL_MAX_TRIES   = 280;   // 280 × 1.2 s = ~5.6 min, matches worker timeout

  const runAsyncPolling = async (q, onProgress, attachmentIds) => {
    // 1) Enqueue
    let startRes;
    try {
      startRes = await fetch(`${API}/api/ora/agent/run-async`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          session_id: sessionId,
          text: q,
          attachment_ids: attachmentIds && attachmentIds.length
            ? attachmentIds : undefined,
        }),
      });
    } catch (e) {
      throw new Error(`network: ${e}`);
    }
    if (startRes.status === 404) {
      // Backend is older — fall back to legacy single-shot path.
      const r = await fetch(`${API}/api/ora/agent/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          session_id: sessionId,
          text: q,
          attachment_ids: attachmentIds && attachmentIds.length
            ? attachmentIds : undefined,
        }),
      });
      return await safeJson(r);
    }
    const startJson = await safeJson(startRes);
    if (!startJson.ok || !startJson.job_id) {
      throw new Error(startJson.error || startJson.detail || "enqueue failed");
    }
    const jobId = startJson.job_id;

    // 2) Poll
    for (let i = 0; i < POLL_MAX_TRIES; i++) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      let pollRes;
      try {
        pollRes = await fetch(
          `${API}/api/ora/agent/status/${encodeURIComponent(jobId)}`,
          { headers: { ...authHeaders() } }
        );
      } catch {
        // transient network blip — keep polling
        continue;
      }
      const j = await safeJson(pollRes);
      if (!j.ok) throw new Error(j.error || j.detail || "status_lost");
      // iter 323l — surface live tool trail to the indicator
      if (typeof onProgress === "function" && Array.isArray(j.tool_calls_so_far)) {
        try { onProgress(j.tool_calls_so_far); } catch { /* never crash poll */ }
      }
      if (j.status === "done")   return j.result || { ok: true, reply: "(empty)" };
      if (j.status === "failed") {
        return { ok: false, error: j.error || "ORA job failed" };
      }
      // else still pending/running — loop
    }
    return { ok: false, error: "ORA job timed out client-side after 5+ min" };
  };

  const send = async () => {
    const q = input.trim();
    if ((!q && attachments.length === 0) || busy) return;
    setError(null);
    // iter 327c — echo attachments + text into history together.
    const attachmentMeta = attachments.map((a) => ({
      kind: a.kind, filename: a.filename, url: a.url, title: a.title,
    }));
    const attachmentIds = attachments.map((a) => a.attachment_id);
    setHistory((h) => [...h, {
      role: "user",
      content: q || (attachments.length === 1
        ? `(sent ${attachments[0].kind})`
        : `(sent ${attachments.length} files)`),
      attachments: attachmentMeta,
      ts: Date.now(),
    }]);
    setInput("");
    setAttachments([]);
    setBusyStartedAt(Date.now());
    setBusyTools([]);
    setBusy(true);
    try {
      const j = await runAsyncPolling(q, setBusyTools, attachmentIds);
      applyTurnResult(j);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
      setBusyTools([]);
    }
  };

  // iter 326uu — pull server-side history so tool_result rows appear
  // in the UI (and the right-side PreviewPane) after each turn.
  const refreshHistory = async () => {
    try {
      const r = await fetch(`${API}/api/ora/agent/history/${sessionId}`,
                            { headers: authHeaders() });
      const j = await safeJson(r);
      if (j.ok && Array.isArray(j.messages)) {
        const ui = [];
        for (const m of j.messages) {
          if (m.role === "user") {
            ui.push({ role: "user", content: m.content || "", ts: 0 });
          } else if (m.role === "assistant") {
            if (m.content) ui.push({ role: "assistant", content: m.content, ts: 0 });
            for (const tc of (m.tool_calls || [])) {
              ui.push({ role: "tool_call", tool: tc.function?.name,
                         args: _safeArgs(tc.function?.arguments) });
            }
          } else if (m.role === "tool") {
            ui.push({ role: "tool_result", tool: m.name,
                       content: m.content || "", ts: 0 });
          }
        }
        setHistory(ui);
      }
    } catch { /* soft */ }
  };

  const applyTurnResult = (j) => {
    if (!j.ok) {
      setError(j.error || j.detail || `HTTP ${j._http_status}`);
      if (j.reply) setHistory((h) => [...h, { role: "assistant",
                                                 content: j.reply, ts: Date.now() }]);
      refreshHistory();   // surface any tool_results that ran before the failure
      return;
    }
    if (j.action_required) {
      const ar = j.action_required;
      if (ar.preamble) {
        setHistory((h) => [...h, { role: "assistant",
                                      content: ar.preamble, ts: Date.now() }]);
      }
      setPending(ar);
      refreshHistory();   // pull in any tool_results from the partial run
      return;
    }
    if (j.reply) {
      setHistory((h) => [...h, { role: "assistant",
                                    content: j.reply, ts: Date.now() }]);
    }
    setPending(null);
    refreshHistory();     // pull in tool_results from the completed run
  };

  const decide = async (approved, note = "") => {
    if (!pending) return;
    const actionSummary = pending.summary;
    const actionTier    = pending.tier;
    setBusy(true); setError(null);
    try {
      const endpoint = approved ? "approve" : "reject";
      const r = await fetch(`${API}/api/ora/agent/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          session_id: sessionId,
          action_id:  pending.action_id,
          note,
        }),
      });
      const j = await safeJson(r);
      // iter 326rr — UX bug fix. Whether the decide() API succeeded or
      // failed (expired / already processed / session mismatch / not
      // authorized), the approval card is DEAD either way. Always clear
      // `pending` here so the UI never leaves a zombie card on screen
      // and the bottom-bar "decide first" lockout lifts immediately.
      // Echo the decision into history AFTER we know the outcome — never
      // pre-emptively (that produced a false "✓ Approved" line when the
      // backend later returned ok:false).
      const ok = j && j.ok !== false;
      const verb = ok
        ? (approved ? "✓ Approved" : "✗ Rejected")
        : (approved ? "⚠️ Approval failed" : "⚠️ Reject failed");
      setHistory((h) => [...h, {
        role: "decision",
        content: `${verb}: ${actionSummary}`,
        tier: actionTier,
        ts: Date.now(),
      }]);
      setPending(null);
      if (!ok) {
        const msg = (j && (j.error || j.detail))
          || `HTTP ${j && j._http_status}`;
        // Friendlier wording for the most common case: row expired
        // between propose and click (default 30-min window).
        const friendly = /not found|already processed|expired/i.test(msg)
          ? "Yeh approval expire ho gayi (30 min window). " +
            "ORA ko dobara bolo — fresh action banegi."
          : msg;
        setError(friendly);
      } else if (j.reply) {
        applyTurnResult(j);
      }
    } catch (e) {
      setPending(null);  // network error also kills the card
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const clearChat = async () => {
    if (!window.confirm("Clear this thread? ORA will start fresh.")) return;
    try {
      await fetch(`${API}/api/ora/agent/clear/${sessionId}`,
                   { method: "POST", headers: authHeaders() });
    } catch { /* soft */ }
    setHistory([]);
    setPending(null);
    setError(null);
    // Fresh thread id
    try {
      const fresh = `ora-${Date.now().toString(36)}`;
      localStorage.setItem(SESSION_KEY, fresh);
      window.location.reload();
    } catch { /* ignore */ }
  };

  return (
    <div data-testid="ora-chat" style={{
      height: "100vh", background: "#0A0A12", color: TEXT,
      padding: "20px 24px 0 24px",
      display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between",
                       alignItems: "center", marginBottom: 16, flex: "0 0 auto" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Crown size={22} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>
              ORA · Autonomous CTO
            </h1>
            <StatusPill busy={busy} pending={!!pending} error={!!error} />
          </div>
          <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 2 }}>
            iter 322fi · Thread {sessionId.slice(-8)} · One chat, no tabs
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button data-testid="incident-link"
                  onClick={() => navigate("/admin/incident-ledger")}
                  style={btn(false)}>
            <ShieldAlert size={12} /> Incidents
          </button>
          {history.length > 0 && (
            <button data-testid="chat-clear" onClick={clearChat} style={btn(false)}>
              <Trash2 size={12} /> Clear
            </button>
          )}
        </div>
      </div>

      {/* iter 326uu — 2-pane layout: chat left, live preview right.
          PreviewPane mirrors the latest tool result so the founder can
          see file diffs / test output / errors WITHOUT scrolling the
          chat. Plan + step tracker stay in the chat column above the
          message list. */}
      <div style={{ flex: "1 1 auto", minHeight: 0, display: "flex",
                       gap: 12 }}>

      {/* LEFT — message list */}
      <div ref={scrollRef}
            style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto",
                      paddingRight: 6 }}>
        {planSteps.length > 0 && (
          <PlanPreview steps={planSteps} completed={planDoneSet} />
        )}
        {busy && !pending && Array.isArray(busyTools) && busyTools.length > 0 && (
          <StepTracker
            steps={busyTools}
            current={busyTools.length}
            label={busyTools[busyTools.length - 1]} />
        )}
        {history.length === 0 && !busy && !pending && (
          <div style={{ color: TEXT_DIM, fontSize: 14, padding: 60,
                          textAlign: "center" }}>
            <Sparkles size={36} color={GOLD} /><br/><br/>
            Bata ORA ko kya karna hai, code edit, deploy, debug, run on Legion,
            check production health. <br/>
            <span style={{ fontSize: 12, color: TEXT_DIM }}>
              Safe tools chalti rahengi automatic; risky ke liye inline approve milega.
            </span>
          </div>
        )}

        {history.map((m, i) => (
          <Message key={i} m={m} i={i} copy={copy} copiedIdx={copiedIdx} />
        ))}

        {pending && (
          <ApprovalCard action={pending}
                         onApprove={() => decide(true)}
                         onReject={() => {
                           const note = window.prompt("Why reject? (optional)", "") || "";
                           decide(false, note);
                         }} />
        )}

        {busy && !pending && (
          <div
            data-testid="ora-working-indicator"
            style={{ color: TEXT_DIM, fontSize: 13, padding: 8,
                     display: "flex", alignItems: "center", gap: 8 }}>
            <Loader2 size={14} className="spin" />
            <span>ORA is working…</span>
            <span data-testid="ora-elapsed-s"
                  style={{ color: GOLD, fontWeight: 600,
                           fontVariantNumeric: "tabular-nums",
                           fontSize: 12 }}>
              {busyElapsedS}s
            </span>
            {busyElapsedS >= 20 && busyElapsedS < 90 && (
              <span style={{ color: TEXT_DIM, fontSize: 11, opacity: 0.8 }}>
                · tool-loop usually 30–60 s on complex queries, hang tight
              </span>
            )}
            {busyElapsedS >= 90 && busyElapsedS < 240 && (
              <span style={{ color: AMBER, fontSize: 11 }}>
                · taking longer than usual, Legion / Groq may be slow
              </span>
            )}
            {busyElapsedS >= 240 && (
              <span style={{ color: RED, fontSize: 11 }}>
                · close to 5 min hard cap, will fail if no result
              </span>
            )}
            {busyTools.length > 0 && (
              <span style={{ display: "inline-flex", flexWrap: "wrap", gap: 4,
                              marginLeft: 4, alignItems: "center" }}>
                {busyTools.slice(-4).map((t, i) => (
                  <span key={`${t}-${i}`}
                        data-testid="ora-progress-chip"
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          padding: "2px 7px",
                          fontSize: 10.5,
                          fontFamily: "monospace",
                          color: GREEN,
                          background: "rgba(103,232,160,0.08)",
                          border: `1px solid ${GREEN}44`,
                          borderRadius: 999,
                          letterSpacing: 0.3,
                        }}>
                    <span style={{ opacity: 0.6 }}>›</span>{t}
                  </span>
                ))}
                {busyTools.length > 4 && (
                  <span style={{ fontSize: 10.5, color: TEXT_DIM, opacity: 0.6 }}>
                    +{busyTools.length - 4} more
                  </span>
                )}
              </span>
            )}
          </div>
        )}
      </div>

      {/* RIGHT — live preview pane (iter 326uu).
          Hidden on narrow viewports; chat stays full-width on mobile. */}
      <div data-testid="ora-preview-column"
           style={{ flex: "0 0 38%", maxWidth: 520, minWidth: 280,
                      display: window.innerWidth < 900 ? "none" : "flex" }}>
        <PreviewPane
          latestTool={latestToolResult?.tool}
          latestResult={latestToolResult?.result} />
      </div>

      </div>{/* close 2-pane flex */}

      {error && (
        <div style={{ background: "rgba(255,118,118,0.10)",
                       border: `1px solid ${RED}`, borderRadius: 10,
                       padding: 10, color: RED, fontSize: 12,
                       margin: "8px 0", flex: "0 0 auto" }}>
          <AlertTriangle size={12} /> {error}
        </div>
      )}

      {/* iter 327c — attachment chips above the input bar */}
      {attachments.length > 0 && (
        <div data-testid="attachment-chips"
             style={{ display: "flex", flexWrap: "wrap", gap: 6,
                        padding: "0 0 8px", flex: "0 0 auto" }}>
          {attachments.map((a) => (
            <span key={a.attachment_id}
                  data-testid={`attachment-chip-${a.kind}`}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 6,
                    padding: "4px 8px", fontSize: 11,
                    background: "rgba(212,175,55,0.10)",
                    border: `1px solid ${GOLD}55`, color: GOLD,
                    borderRadius: 999, fontFamily: "monospace",
                  }}>
              {a.kind === "image" && "🖼"}
              {a.kind === "pdf"   && "📄"}
              {a.kind === "doc"   && "📝"}
              {a.kind === "video" && "🎥"}
              {a.filename || a.url || a.kind}
              <button onClick={() => removeAttachment(a.attachment_id)}
                      data-testid="attachment-remove"
                      style={{ background: "transparent", border: "none",
                                color: GOLD, cursor: "pointer", padding: 0,
                                marginLeft: 2 }}>
                <X size={11} />
              </button>
            </span>
          ))}
          {uploading && (
            <span style={{ color: TEXT_DIM, fontSize: 11,
                              display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Loader2 size={11} className="spin" /> uploading…
            </span>
          )}
        </div>
      )}

      {/* Input */}
      <div style={{ display: "flex", gap: 8, padding: "12px 0 18px",
                      flex: "0 0 auto", alignItems: "center" }}>
        {/* iter 327c — single "+" button. One tap opens picker.
            `capture="environment"` makes mobile offer camera too. */}
        <input ref={fileInputRef}
                type="file"
                data-testid="ora-attachment-input"
                accept="image/*,application/pdf,.doc,.docx,.txt,.md,.csv,video/*"
                onChange={handleFileChosen}
                style={{ display: "none" }} />
        <button data-testid="ora-attach-btn"
                onClick={() => fileInputRef.current && fileInputRef.current.click()}
                disabled={busy || !!pending || uploading}
                title="Attach a photo, document, video, or take a picture"
                style={{
                  width: 38, height: 38, borderRadius: 999,
                  background: "rgba(212,175,55,0.06)",
                  border: `1px solid ${GOLD}55`, color: GOLD,
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  cursor: (busy || !!pending || uploading) ? "not-allowed" : "pointer",
                  flex: "0 0 auto",
                }}>
          {uploading ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
        </button>
        <input data-testid="chat-input"
                value={input}
                disabled={busy || !!pending}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder={pending
                  ? "Pending approval above — decide first"
                  : "Bata kya karna hai (Hindi/English mix chalega)…"}
                style={chatInput(busy || !!pending)} />
        <button data-testid="chat-send"
                disabled={busy || !!pending || (!input.trim() && attachments.length === 0)}
                onClick={send}
                style={btn(true, busy || !!pending || (!input.trim() && attachments.length === 0))}>
          <Send size={14} /> Send
        </button>
      </div>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        @keyframes robotBob {
          0%, 100% { transform: translateY(0) rotate(0deg); }
          25%      { transform: translateY(-2px) rotate(-6deg); }
          50%      { transform: translateY(0) rotate(0deg); }
          75%      { transform: translateY(-1px) rotate(6deg); }
        }
      `}</style>
    </div>
  );
}

function Message({ m, i, copy, copiedIdx }) {
  if (m.role === "user") {
    return (
      <div>
        <Bubble side="right" colorBg="rgba(212,175,55,0.16)" label="YOU"
                content={m.content} idx={i} copy={copy} copiedIdx={copiedIdx} />
        {Array.isArray(m.attachments) && m.attachments.length > 0 && (
          <div data-testid={`user-attachments-${i}`}
               style={{ display: "flex", flexWrap: "wrap", gap: 6,
                          justifyContent: "flex-end",
                          marginTop: -4, marginBottom: 8 }}>
            {m.attachments.map((a, j) => (
              <a key={j}
                 href={a.url || "#"}
                 target="_blank"
                 rel="noopener noreferrer"
                 data-testid={`attachment-preview-${a.kind}`}
                 style={{
                   display: "inline-flex", alignItems: "center", gap: 6,
                   padding: "4px 8px", fontSize: 11,
                   background: "rgba(212,175,55,0.08)",
                   border: "1px solid rgba(212,175,55,0.35)",
                   borderRadius: 8, color: "#D4AF37",
                   fontFamily: "monospace",
                   textDecoration: "none",
                 }}>
                {a.kind === "image" && "🖼"}
                {a.kind === "pdf"   && "📄"}
                {a.kind === "doc"   && "📝"}
                {a.kind === "video" && "🎥"}
                {a.kind === "link"  && "🔗"}
                {a.filename || a.title || a.url || a.kind}
              </a>
            ))}
          </div>
        )}
      </div>
    );
  }
  if (m.role === "assistant") {
    return (
      <Bubble side="left" colorBg="rgba(255,255,255,0.05)" label="ORA"
              content={m.content} idx={i} copy={copy} copiedIdx={copiedIdx} />
    );
  }
  if (m.role === "tool_call") {
    return (
      <ToolBadge icon={<Wand2 size={11} />} label="ORA called tool"
                  tool={m.tool} args={m.args} />
    );
  }
  if (m.role === "tool_result") {
    // iter 326uu — smart, tool-aware rendering replaces the old
    // generic JSON-dump ToolBadge. content may be a JSON string
    // (from server history) or already an object (from live polls).
    const parsed = (() => {
      if (m.result && typeof m.result === "object") return m.result;
      if (!m.content) return { ok: true };
      if (typeof m.content === "object") return m.content;
      try { return JSON.parse(m.content); } catch { return { raw: String(m.content) }; }
    })();
    return <SmartToolResult tool={m.tool} result={parsed} />;
  }
  if (m.role === "decision") {
    const c = m.tier && TIER_STYLES[m.tier] ? TIER_STYLES[m.tier].color : TEXT_DIM;
    return (
      <div style={{ padding: "6px 10px", color: c, fontSize: 11.5,
                       textTransform: "uppercase", letterSpacing: 0.3 }}>
        {m.content}
      </div>
    );
  }
  return null;
}

function Bubble({ side, colorBg, label, content, idx, copy, copiedIdx }) {
  return (
    <div data-testid={`msg-${idx}`}
          style={{ display: "flex",
                    justifyContent: side === "right" ? "flex-end" : "flex-start",
                    marginBottom: 10 }}>
      <div style={{ background: colorBg, border: `1px solid ${BORDER}`,
                       padding: "8px 12px", borderRadius: 12, maxWidth: "72%" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center",
                         justifyContent: "space-between" }}>
          <div style={{ color: TEXT_DIM, fontSize: 10,
                          textTransform: "uppercase", letterSpacing: 0.4 }}>
            {label}
          </div>
          <button data-testid={`msg-copy-${idx}`}
                   onClick={() => copy(String(content ?? ""), idx)}
                   title="Copy"
                   style={{
                     background: "transparent", border: "none",
                     cursor: "pointer", padding: 2, gap: 4, display: "flex",
                     alignItems: "center",
                     color: copiedIdx === idx ? GREEN : TEXT_DIM,
                     fontSize: 10, fontWeight: 600,
                   }}>
            {copiedIdx === idx ? <Check size={12} /> : <Copy size={12} />}
            {copiedIdx === idx ? "Copied" : "Copy"}
          </button>
        </div>
        <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap",
                         wordBreak: "break-word", marginTop: 4 }}>
          {content}
        </div>
      </div>
    </div>
  );
}

function ToolBadge({ icon, label, tool, args, payload }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ margin: "4px 0", padding: "4px 8px",
                    background: "rgba(212,175,55,0.04)",
                    border: `1px dashed ${BORDER}`, borderRadius: 8,
                    fontSize: 11, color: TEXT_DIM, fontFamily: "ui-monospace,monospace" }}>
      <div onClick={() => setOpen((v) => !v)}
            style={{ cursor: "pointer", display: "flex",
                      alignItems: "center", gap: 6 }}>
        <ChevronRight size={10}
                       style={{ transform: open ? "rotate(90deg)" : "none",
                                 transition: "transform 0.15s" }} />
        {icon}
        <span>{label}: <strong style={{ color: GOLD }}>{tool}</strong></span>
      </div>
      {open && (
        <pre style={{
          marginTop: 6, padding: 8, borderRadius: 6,
          background: "rgba(0,0,0,0.4)", color: TEXT,
          fontSize: 10.5, lineHeight: 1.5,
          maxHeight: 200, overflow: "auto", whiteSpace: "pre-wrap",
        }}>
          {args !== undefined
            ? JSON.stringify(args, null, 2)
            : (payload || "(empty)").slice(0, 1800)}
        </pre>
      )}
    </div>
  );
}

function ApprovalCard({ action, onApprove, onReject }) {
  const t = TIER_STYLES[action.tier] || TIER_STYLES.tier2_approve;
  return (
    <div data-testid="approval-card"
          style={{ ...GLASS, padding: 14, margin: "10px 0",
                    background: t.bg, borderColor: t.color }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                       alignItems: "center", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Wrench size={14} color={t.color} />
          <span style={{ color: t.color, fontSize: 11, fontWeight: 700,
                            textTransform: "uppercase", letterSpacing: 0.4 }}>
            {t.label} · ORA wants to run
          </span>
        </div>
        <span style={{ color: TEXT_DIM, fontSize: 10, fontFamily: "monospace" }}>
          {action.action_id?.slice(0, 8)}
        </span>
      </div>

      <div style={{ fontSize: 14, color: TEXT, marginBottom: 6, fontWeight: 600 }}>
        {action.tool}
      </div>
      <div style={{ fontSize: 13, color: TEXT, marginBottom: 10 }}>
        {action.summary}
      </div>

      {action.args && Object.keys(action.args).length > 0 && (
        <details style={{ marginBottom: 12 }}>
          <summary style={{ color: TEXT_DIM, fontSize: 11, cursor: "pointer" }}>
            View args
          </summary>
          <pre style={{
            marginTop: 6, padding: 8, borderRadius: 6,
            background: "rgba(0,0,0,0.4)", color: TEXT,
            fontSize: 10.5, lineHeight: 1.5,
            maxHeight: 180, overflow: "auto", whiteSpace: "pre-wrap",
            fontFamily: "ui-monospace,monospace",
          }}>
            {JSON.stringify(action.args, null, 2)}
          </pre>
        </details>
      )}

      <div style={{ display: "flex", gap: 8 }}>
        <button data-testid="approve-btn" onClick={onApprove}
                 style={{ ...btn(true), background: t.color, color: "#0A0A12",
                           borderColor: t.color, padding: "8px 16px" }}>
          <Check size={14} /> Approve
        </button>
        <button data-testid="reject-btn" onClick={onReject}
                 style={{ ...btn(false), padding: "8px 16px" }}>
          <X size={14} /> Reject
        </button>
        <ExpiryCountdown expiresAt={action.expires_at}
                         fallbackMin={action.expires_in_minutes || 60} />
      </div>
    </div>
  );
}

// iter 326tt — live countdown so the founder can SEE when an approval
// is about to die. Beats the old hard-coded "Expires in 30m" literal
// that never ticked. Computes remaining seconds from expires_at
// every second; falls back to the static minute count if backend
// didn't send expires_at (older sessions).
function ExpiryCountdown({ expiresAt, fallbackMin }) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  if (!expiresAt) {
    return (
      <span style={{ marginLeft: "auto", color: TEXT_DIM, fontSize: 10,
                       alignSelf: "center" }}>
        Expires in {fallbackMin}m
      </span>
    );
  }
  const target = new Date(expiresAt).getTime();
  const remaining = Math.max(0, target - now);
  const mins = Math.floor(remaining / 60000);
  const secs = Math.floor((remaining % 60000) / 1000);
  // Colour shifts: gold → amber (under 5 min) → red (under 1 min)
  let colour = TEXT_DIM;
  if (remaining <= 60 * 1000)        colour = RED;
  else if (remaining <= 5 * 60 * 1000) colour = AMBER;
  const label = remaining === 0
    ? "Expired"
    : `Expires in ${mins}:${String(secs).padStart(2, "0")}`;
  return (
    <span data-testid="approval-expiry-countdown"
           style={{ marginLeft: "auto", color: colour, fontSize: 10,
                     alignSelf: "center", fontVariantNumeric: "tabular-nums" }}>
      {label}
    </span>
  );
}

function _safeArgs(raw) {
  if (raw == null) return {};
  if (typeof raw === "object") return raw;
  try { return JSON.parse(raw); }
  catch { return { _raw: String(raw).slice(0, 200) }; }
}

/**
 * StatusPill — small robot 🤖 badge next to the title.
 * - Idle (default): grey "🤖 IDLE"
 * - Working: gold pulse "🤖 WORKING…" with shimmer
 * - Awaiting approval: amber "🤖 NEEDS YOU"
 * - Error: red "🤖 STUCK"
 */
function StatusPill({ busy, pending, error }) {
  let label = "IDLE", color = TEXT_DIM, pulse = false;
  if (error)       { label = "STUCK";      color = RED; }
  else if (pending){ label = "NEEDS YOU";  color = AMBER; pulse = true; }
  else if (busy)   { label = "WORKING…";   color = GOLD;  pulse = true; }
  return (
    <span data-testid="ora-status-pill"
           style={{
             display: "inline-flex", alignItems: "center", gap: 6,
             padding: "3px 10px",
             background: `${color}22`,
             border: `1px solid ${color}66`,
             borderRadius: 999,
             fontSize: 10.5, fontWeight: 700,
             color, letterSpacing: 0.5, textTransform: "uppercase",
             marginLeft: 6,
             position: "relative", overflow: "hidden",
           }}>
      <span style={{
        fontSize: 12, display: "inline-block",
        animation: pulse ? "robotBob 1.4s ease-in-out infinite" : "none",
      }}>🤖</span>
      <span style={{ position: "relative", zIndex: 1 }}>{label}</span>
      {pulse && (
        <span style={{
          position: "absolute", inset: 0,
          background: `linear-gradient(90deg, transparent, ${color}33, transparent)`,
          animation: "shimmer 1.8s linear infinite",
          pointerEvents: "none",
        }} />
      )}
    </span>
  );
}

function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 12px", fontSize: 12, fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1, transition: "all 0.15s",
  };
}

function chatInput(disabled) {
  return {
    flex: 1, padding: "10px 14px",
    background: "rgba(0,0,0,0.45)",
    color: TEXT, border: `1px solid ${BORDER}`, borderRadius: 10,
    fontSize: 13, outline: "none",
    opacity: disabled ? 0.6 : 1,
  };
}
