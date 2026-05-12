/**
 * OraChat — iter 322es
 * 3-tab ORA experience for the founder:
 *   Tab 1: General Chat    — converse with ORA via the public ORA endpoint
 *   Tab 2: CTO Mode        — quick action buttons → invoke ora-tools → live output
 *   Tab 3: Files & Uploads — drag-drop multi-format, analyze with ORA
 *
 * Route: /admin/ora-chat
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Crown, MessageSquare, Wrench, FileUp, Send, Upload,
  Trash2, ChevronRight, ExternalLink, Sparkles, Loader2,
  AlertTriangle, FileText, FileImage, FileAudio, FileVideo, FileQuestion,
  RotateCcw, Copy, Check,
} from "lucide-react";

// Persistence keys (versioned so we can bump schema later without breaking)
const LS_THREAD_KEY  = "aurem.ora-chat.thread.v1";
const LS_HISTORY_KEY = "aurem.ora-chat.history.v1";
const HISTORY_CAP    = 200;  // last N messages persisted (~quota safe)

const API = process.env.REACT_APP_BACKEND_URL || "";

const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.18)";
const GREEN = "#67E8A0";
const RED = "#FF7676";
const AMBER = "#FFB36B";

const GLASS = {
  background: "linear-gradient(160deg, rgba(22,22,32,0.78), rgba(10,10,18,0.86))",
  backdropFilter: "blur(22px) saturate(160%)",
  WebkitBackdropFilter: "blur(22px) saturate(160%)",
  border: `1px solid ${BORDER}`,
  borderRadius: 18,
  boxShadow: "0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
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

/**
 * safeJson — never throws "Unexpected token '<'".
 * Reads body as text, attempts JSON parse, and on failure surfaces
 * the actual HTTP status + a short preview so the founder can see WHAT
 * went wrong (502 from nginx, HTML login page, timeout, etc).
 *
 * Always resolves with a plain object. Caller can rely on `.ok` boolean.
 */
async function safeJson(r) {
  const status = r?.status ?? 0;
  let text = "";
  try { text = await r.text(); } catch { /* network mid-read */ }
  // Try JSON parse
  try {
    const j = text ? JSON.parse(text) : {};
    if (typeof j === "object" && j !== null) {
      if (!("ok" in j)) j.ok = r.ok;
      j._http_status = status;
      return j;
    }
    return { ok: r.ok, _http_status: status, value: j };
  } catch (_e) {
    const preview = (text || "").replace(/\s+/g, " ").trim().slice(0, 220);
    const looksLikeHtml = /^\s*<(?:!doctype|html|head|body)/i.test(text);
    const reason = !r.ok
      ? `HTTP ${status} ${r.statusText || ""}`.trim()
      : looksLikeHtml
        ? "Server returned an HTML page (likely 502/504/gateway timeout)"
        : "Response was not valid JSON";
    return {
      ok: false,
      _http_status: status,
      error: reason,
      detail: preview ? `${reason} — body preview: ${preview}` : reason,
    };
  }
}

export default function OraChat() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("chat");
  return (
    <div data-testid="ora-chat"
         style={{
           height: "100vh", background: "#0A0A12", color: TEXT,
           padding: "24px 24px 0 24px",
           display: "flex", flexDirection: "column", overflow: "hidden",
         }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18, flex: "0 0 auto" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Crown size={26} color={GOLD} />
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700 }}>ORA</h1>
          </div>
          <p style={{ color: TEXT_DIM, fontSize: 13, marginTop: 6 }}>
            Chat · CTO Mode (16 tools live) · Files & Uploads
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button data-testid="open-cockpit" onClick={() => navigate("/admin/ora-cto")} style={btn(false)}>
            Cockpit <ExternalLink size={12} />
          </button>
          <button data-testid="back-btn" onClick={() => navigate("/admin/boardroom")} style={btn(false)}>← Back</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 14, flex: "0 0 auto" }}>
        {[
          ["chat", "General Chat", MessageSquare],
          ["cto",  "CTO Mode",     Wrench],
          ["files", "Files & Uploads", FileUp],
        ].map(([k, label, Icon]) => (
          <button data-testid={`tab-${k}`} key={k} onClick={() => setTab(k)}
                  style={tabBtn(tab === k)}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      <div style={{ flex: "1 1 auto", minHeight: 0, overflow: "auto", paddingBottom: 24 }}>
        {tab === "chat"  && <ChatPane />}
        {tab === "cto"   && <CTOPane />}
        {tab === "files" && <FilesPane />}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 1 — General Chat
// ──────────────────────────────────────────────────────────────────────
function ChatPane() {
  // Persistent thread id — same across page reloads/route returns
  const [sessionId] = useState(() => {
    try {
      let id = localStorage.getItem(LS_THREAD_KEY);
      if (!id) {
        id = `ora-chat-${Date.now().toString(36)}`;
        localStorage.setItem(LS_THREAD_KEY, id);
      }
      return id;
    } catch { return `ora-chat-${Date.now().toString(36)}`; }
  });

  // Hydrated history from localStorage so chat never vanishes on return
  const [history, setHistory] = useState(() => {
    try {
      const raw = localStorage.getItem(LS_HISTORY_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch { return []; }
  });
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState(null);
  const scrollRef = useRef(null);

  // Persist on every change (capped, fire-and-forget)
  useEffect(() => {
    try {
      const trimmed = history.slice(-HISTORY_CAP);
      localStorage.setItem(LS_HISTORY_KEY, JSON.stringify(trimmed));
    } catch { /* quota / private mode — ignore */ }
  }, [history]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history, busy]);

  const copyToClipboard = async (text, idx) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Legacy fallback
        const ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand("copy"); ta.remove();
      }
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx((v) => (v === idx ? null : v)), 1500);
    } catch { /* clipboard blocked — silent */ }
  };

  const clearChat = () => {
    if (!confirm("Clear entire chat history? This cannot be undone.")) return;
    setHistory([]);
    try {
      localStorage.removeItem(LS_HISTORY_KEY);
      // Fresh thread id so server-side memory also splits
      const fresh = `ora-chat-${Date.now().toString(36)}`;
      localStorage.setItem(LS_THREAD_KEY, fresh);
    } catch { /* ignore */ }
  };

  const send = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setHistory((h) => [...h, { role: "user", content: q, ts: Date.now() }]);
    setInput("");
    setBusy(true);
    try {
      const t0 = Date.now();
      const r = await fetch(`${API}/api/public/ora/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ text: q, session_id: sessionId }),
      });
      const j = await safeJson(r);
      const isErr = j.ok === false;
      setHistory((h) => [...h, {
        role: isErr ? "error" : "assistant",
        content: j.reply || j.detail || j.error || JSON.stringify(j),
        provider: j.provider || (isErr ? `HTTP ${j._http_status}` : undefined),
        ms: Date.now() - t0,
        ts: Date.now(),
      }]);
    } catch (e) {
      setHistory((h) => [...h, { role: "error", content: String(e), ts: Date.now() }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{
      ...GLASS, padding: 16,
      display: "flex", flexDirection: "column", gap: 12,
      height: "100%", minHeight: 0,
    }}>
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flex: "0 0 auto",
      }}>
        <div style={{ color: TEXT_DIM, fontSize: 11, textTransform: "uppercase", letterSpacing: 0.4 }}>
          Thread · {sessionId.slice(-8)} · {history.length} msgs · saved locally
        </div>
        {history.length > 0 && (
          <button data-testid="chat-clear-btn" onClick={clearChat} style={btn(false)}>
            <Trash2 size={12} /> Clear chat
          </button>
        )}
      </div>

      <div ref={scrollRef} style={{ flex: "1 1 auto", minHeight: 0, overflowY: "auto", paddingRight: 6 }}>
        {history.length === 0 && (
          <div style={{ color: TEXT_DIM, fontSize: 13, padding: 24, textAlign: "center" }}>
            <Sparkles size={28} color={GOLD} /> <br />
            Talk to ORA. She has access to AUREM's full skill library + Sovereign Node fallbacks.
            <div style={{ marginTop: 8, fontSize: 11 }}>Chat history saves automatically.</div>
          </div>
        )}
        {history.map((m, i) => (
          <div data-testid={`msg-${i}`} key={i}
               style={{
                 marginBottom: 10,
                 display: "flex",
                 justifyContent: m.role === "user" ? "flex-end" : "flex-start",
               }}>
            <div style={{
              background: m.role === "user"
                ? "rgba(212,175,55,0.16)"
                : m.role === "error" ? "rgba(255,118,118,0.16)" : "rgba(255,255,255,0.05)",
              border: `1px solid ${BORDER}`,
              padding: "8px 12px", borderRadius: 12, maxWidth: "70%",
              position: "relative",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                <div style={{ color: TEXT_DIM, fontSize: 10, marginBottom: 4,
                                textTransform: "uppercase" }}>
                  {m.role === "user" ? "you" : m.role === "error" ? "error" : "ORA"}
                  {m.provider && <span style={{ marginLeft: 6 }}>· {m.provider}</span>}
                  {m.ms && <span style={{ marginLeft: 6 }}>· {m.ms}ms</span>}
                </div>
                <button data-testid={`msg-copy-${i}`}
                        onClick={() => copyToClipboard(String(m.content ?? ""), i)}
                        title="Copy message"
                        style={{
                          background: "transparent", border: "none", cursor: "pointer",
                          color: copiedIdx === i ? GREEN : TEXT_DIM,
                          padding: 2, display: "flex", alignItems: "center", gap: 4,
                          fontSize: 10, fontWeight: 600, textTransform: "uppercase",
                        }}>
                  {copiedIdx === i ? <Check size={12} /> : <Copy size={12} />}
                  {copiedIdx === i ? "Copied" : "Copy"}
                </button>
              </div>
              <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{m.content}</div>
            </div>
          </div>
        ))}
        {busy && (
          <div style={{ color: TEXT_DIM, fontSize: 12 }}>
            <Loader2 size={14} className="spin" /> ORA is thinking…
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 8, flex: "0 0 auto" }}>
        <input data-testid="chat-input" value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Ask ORA anything — bypass with `cto:` prefix to invoke a tool"
                style={chatInput} />
        <button data-testid="chat-send" disabled={busy || !input.trim()} onClick={send}
                style={btn(true, busy || !input.trim())}>
          <Send size={14} /> Send
        </button>
      </div>
      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 2 — CTO Mode (+ Preview / Deploy / Save / Rollback workflow)
// ──────────────────────────────────────────────────────────────────────
const QUICK_ACTIONS = [
  { id: "view_file",       label: "Read File",          tool: "view_file",
    argsPrompt: { path: "/app/memory/PRD.md" } },
  { id: "grep",            label: "Grep",               tool: "grep_codebase",
    argsPrompt: { pattern: "TODO", path: "/app/backend", max_results: 12 } },
  { id: "shell",           label: "Shell",              tool: "shell_exec",
    argsPrompt: { command: "git", args: ["log", "--oneline", "-5"] } },
  { id: "restart",         label: "Restart Service",    tool: "restart_service",
    argsPrompt: { service: "backend" } },
  { id: "council",         label: "Council Consult",    tool: "council_consult",
    argsPrompt: { question: "Is bumping max_tokens to 1000 safe?", roles: ["security", "backend"] } },
  { id: "health",          label: "Health Check",       tool: "health_check",
    argsPrompt: {} },
  { id: "git_log",         label: "Git Log",            tool: "git_log",
    argsPrompt: { n: 5 } },
  { id: "lint",            label: "Lint Python",        tool: "lint_python",
    argsPrompt: { path: "/app/backend/services/ora_tools.py" } },
  { id: "code_review",     label: "Code Review",        tool: "code_review",
    argsPrompt: { path: "/app/backend/services/ora_tools.py" } },
  { id: "security_scan",   label: "Security Scan",      tool: "security_scan",
    argsPrompt: { path: "/app/backend/routers/auth_router.py" } },
  { id: "db_count",        label: "DB Count",           tool: "db_count",
    argsPrompt: { collection: "ora_tool_invocations" } },
  { id: "propose_commit",  label: "Propose Commit",     tool: "propose_commit",
    argsPrompt: { title: "docs: example proposal",
                   body:  "Example body",
                   file_paths: ["/app/memory/PRD.md"],
                   rationale: "Smoke-test propose_commit from the CTO tab." } },
];

function CTOPane() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [argsBox, setArgsBox] = useState("");
  const [chosen, setChosen] = useState(null);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState(null);
  const [backups, setBackups] = useState([]);
  const [brief, setBrief] = useState(null);
  const [briefBusy, setBriefBusy] = useState(false);
  const navigate = useNavigate();

  const loadRecent = async () => {
    try {
      const r = await fetch(`${API}/api/ora-tools/invocations?limit=10`,
                             { headers: authHeaders() });
      const j = await safeJson(r);
      if (j?.ok) setRecent(j.invocations || []);
    } catch { /* soft fail */ }
  };
  const loadBackups = async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora-rollback/list?limit=10`,
                             { headers: authHeaders() });
      const j = await safeJson(r);
      if (j?.ok) setBackups(j.rows || []);
    } catch { /* soft fail */ }
  };
  const runMorningBrief = async () => {
    setBriefBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/ora-cto/morning-brief`,
                             { headers: authHeaders() });
      const j = await safeJson(r);
      if (j?.ok) setBrief(j);
      else setError(j?.detail || "morning-brief failed");
    } catch (e) {
      setError(String(e));
    } finally {
      setBriefBusy(false);
    }
  };
  useEffect(() => {
    loadRecent(); loadBackups();
    const t = setInterval(() => { loadRecent(); loadBackups(); }, 12000);
    return () => clearInterval(t);
  }, []);

  const pickAction = (a) => {
    setChosen(a);
    setArgsBox(JSON.stringify(a.argsPrompt, null, 2));
    setResult(null);
    setError(null);
  };

  const execute = async () => {
    if (!chosen) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const args = argsBox.trim() ? JSON.parse(argsBox) : {};
      const r = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: chosen.tool, args }),
      });
      const j = await safeJson(r);
      setResult(j);
      if (j.ok === false && j.error) setError(j.detail || j.error);
      loadRecent();
      loadBackups();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const deployAfterEdit = async () => {
    // Chain: lint_python (if the result has a path) → restart backend → health_check
    if (!result || !result.path) return;
    setBusy(true);
    setError(null);
    const steps = [];
    try {
      const linted = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: "lint_python", args: { path: result.path } }),
      }).then(safeJson);
      steps.push({ step: "lint_python", ok: linted.ok, summary: linted.error_count ?? linted.error });
      const restarted = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: "restart_service", args: { service: "backend" } }),
      }).then(safeJson);
      steps.push({ step: "restart_service", ok: restarted.ok });
      // Wait a tick for the supervisor to bring things back
      await new Promise((res) => setTimeout(res, 4000));
      const hc = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: "health_check", args: {} }),
      }).then(safeJson);
      steps.push({ step: "health_check", ok: hc.ok });
      setResult({ ...result, deploy_steps: steps });
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
      loadRecent();
    }
  };

  const saveToGithub = async () => {
    if (!result || !result.path) return;
    setBusy(true);
    setError(null);
    try {
      const body = {
        tool: "propose_commit",
        args: {
          title: `ora: edit ${result.path.split("/").pop()}`,
          body: "Automated propose_commit from ORA CTO Mode.",
          file_paths: [result.path],
          rationale: "ORA-driven edit promoted to commit proposal via Save to GitHub button.",
        },
      };
      const r = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
      const j = await safeJson(r);
      if (j?.ok && j?.proposal_id) {
        setResult({ ...result, proposal_id: j.proposal_id });
        navigate("/admin/git-gate");
      } else {
        setError(j?.error || "propose_commit failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const rollback = async (backupName) => {
    if (!confirm(`Restore ${backupName}? This overwrites the current file.`)) return;
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/admin/ora-rollback/restore`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ backup_name: backupName, restart_service: "backend" }),
      });
      const j = await safeJson(r);
      setResult({ rollback: j });
      loadBackups(); loadRecent();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // Did the latest result come from a safe_edit_with_council that PASSED?
  const canDeploy = !!(result && result.ok && result.path && result.backup_path);
  const canSaveToGithub = canDeploy;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 14 }}>
      {/* LEFT: quick actions + output */}
      <div style={{ display: "grid", gap: 12 }}>
        {/* Morning Brief banner */}
        <div style={{ ...GLASS, padding: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 14 }}>☀️ Morning Brief</div>
              <div style={{ color: TEXT_DIM, fontSize: 11 }}>
                git log · DB counts · overrides · failures · customers · pending proposals
              </div>
            </div>
            <button data-testid="morning-brief-btn" onClick={runMorningBrief}
                    disabled={briefBusy} style={btn(true, briefBusy)}>
              {briefBusy ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}
              {brief ? "Refresh brief" : "Run brief"}
            </button>
          </div>
          {brief && (
            <pre data-testid="morning-brief-output"
                  style={{
                    marginTop: 12, padding: 12, borderRadius: 8,
                    background: "rgba(0,0,0,0.4)", border: `1px solid ${BORDER}`,
                    color: TEXT, fontSize: 11.5, lineHeight: 1.5,
                    whiteSpace: "pre-wrap", maxHeight: 360, overflow: "auto",
                    fontFamily: "ui-monospace,monospace",
                  }}>
              {brief.markdown}
            </pre>
          )}
        </div>

        <div style={{ ...GLASS, padding: 16 }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, textTransform: "uppercase", marginBottom: 8 }}>
            Quick actions
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            {QUICK_ACTIONS.map((a) => (
              <button data-testid={`quick-${a.id}`} key={a.id}
                      onClick={() => pickAction(a)}
                      style={{
                        ...quickBtn,
                        borderColor: chosen?.id === a.id ? GOLD : BORDER,
                        background: chosen?.id === a.id ? "rgba(212,175,55,0.12)" : "rgba(255,255,255,0.04)",
                      }}>
                {a.label}
              </button>
            ))}
          </div>
          {chosen && (
            <div style={{ marginTop: 14 }}>
              <div style={{ color: TEXT_DIM, fontSize: 11, marginBottom: 4 }}>
                Tool: <code style={{ color: GOLD }}>{chosen.tool}</code>
              </div>
              <textarea data-testid="cto-args-box"
                         value={argsBox}
                         onChange={(e) => setArgsBox(e.target.value)}
                         style={{
                           width: "100%", minHeight: 110,
                           background: "rgba(0,0,0,0.4)", color: TEXT,
                           border: `1px solid ${BORDER}`, borderRadius: 8,
                           padding: 10, fontSize: 12,
                           fontFamily: "ui-monospace,monospace",
                         }} />
              <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                <button data-testid="cto-execute-btn" disabled={busy} onClick={execute} style={btn(true, busy)}>
                  {busy ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
                  Execute (PREVIEW)
                </button>
                {canDeploy && (
                  <button data-testid="cto-deploy-btn" disabled={busy} onClick={deployAfterEdit} style={btn(false, busy)}>
                    Deploy: lint → restart → health
                  </button>
                )}
                {canSaveToGithub && (
                  <button data-testid="cto-save-github-btn" disabled={busy} onClick={saveToGithub} style={btn(false, busy)}>
                    Save to GitHub
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <div style={{ ...GLASS, padding: 16, minHeight: 320 }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, textTransform: "uppercase", marginBottom: 8 }}>
            Live tool output
          </div>
          {error && (
            <div style={{ color: RED, fontSize: 13 }}>
              <AlertTriangle size={14} /> {error}
            </div>
          )}
          {!result && !error && (
            <div style={{ color: TEXT_DIM, fontSize: 13, padding: 12 }}>
              Pick an action above and hit Execute.
            </div>
          )}
          {result && (
            <pre style={{
              margin: 0, fontSize: 12, whiteSpace: "pre-wrap",
              fontFamily: "ui-monospace,monospace", color: TEXT,
              maxHeight: 460, overflow: "auto",
            }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {/* RIGHT: recent invocations + rollback panel */}
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ ...GLASS, padding: 16 }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, textTransform: "uppercase", marginBottom: 8 }}>
            Recent invocations
          </div>
          {recent.length === 0 ? (
            <div style={{ color: TEXT_DIM, fontSize: 13 }}>No tool calls yet.</div>
          ) : recent.map((r, i) => (
            <div data-testid={`recent-${i}`} key={i}
                 style={{ padding: 8, borderBottom: `1px solid rgba(212,175,55,0.06)`, fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600 }}>{r.tool}</span>
                <span style={{ color: r.ok ? GREEN : RED }}>{r.ok ? "✓" : "✗"}</span>
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 11 }}>
                {(r.ts || "").slice(0, 19)} · {r.elapsed_ms ?? "?"} ms
              </div>
            </div>
          ))}
        </div>

        <div style={{ ...GLASS, padding: 16 }}>
          <div style={{ color: TEXT_DIM, fontSize: 12, textTransform: "uppercase", marginBottom: 8 }}>
            Rollback (last 10 backups)
          </div>
          {backups.length === 0 ? (
            <div style={{ color: TEXT_DIM, fontSize: 13 }}>No backups available.</div>
          ) : backups.map((b, i) => (
            <div data-testid={`backup-${i}`} key={b.backup_name}
                 style={{ padding: 8, borderBottom: `1px solid rgba(212,175,55,0.06)`, fontSize: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 12, color: TEXT,
                              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {b.original_path}
              </div>
              <div style={{ color: TEXT_DIM, fontSize: 10 }}>
                {b.mtime?.slice(0, 19)} · {Math.round((b.size_bytes || 0) / 1024)} KB
              </div>
              <button data-testid={`rollback-${i}`} onClick={() => rollback(b.backup_name)}
                      style={{ ...btn(false), marginTop: 4, fontSize: 11, padding: "4px 8px" }}>
                <RotateCcw size={11} /> Rollback
              </button>
            </div>
          ))}
        </div>
      </div>
      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 3 — Files & Uploads
// ──────────────────────────────────────────────────────────────────────
function FilesPane() {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [drag, setDrag] = useState(false);
  const [analyzing, setAnalyzing] = useState(null);
  const [analysis, setAnalysis] = useState({});
  const [question, setQuestion] = useState("");

  const load = async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora-files/list?limit=30`,
                             { headers: authHeaders() });
      const j = await safeJson(r);
      if (j?.ok) setFiles(j.rows || []);
    } catch (e) { /* soft fail */ }
  };
  useEffect(() => { load(); }, []);

  const upload = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    setBusy(true);
    setError(null);
    for (const f of fileList) {
      try {
        const form = new FormData();
        form.append("file", f);
        form.append("folder", "chat");
        const r = await fetch(`${API}/api/admin/ora-files/upload`, {
          method: "POST", body: form, headers: authHeaders(),
        });
        const j = await safeJson(r);
        if (!r.ok) setError(j.detail || j.error || `upload failed for ${f.name}`);
      } catch (e) {
        setError(String(e));
      }
    }
    load();
    setBusy(false);
  };

  const analyze = async (id) => {
    setAnalyzing(id);
    try {
      const r = await fetch(`${API}/api/admin/ora-files/${id}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ question }),
      });
      const j = await safeJson(r);
      setAnalysis((m) => ({ ...m, [id]: j }));
      load();
    } catch (e) {
      setAnalysis((m) => ({ ...m, [id]: { ok: false, error: String(e) } }));
    } finally {
      setAnalyzing(null);
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this file from /mnt/uploads + index?")) return;
    try {
      await fetch(`${API}/api/admin/ora-files/${id}`, {
        method: "DELETE", headers: authHeaders(),
      });
      load();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div data-testid="drop-zone"
           onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
           onDragLeave={() => setDrag(false)}
           onDrop={(e) => {
             e.preventDefault(); setDrag(false);
             upload(Array.from(e.dataTransfer.files || []));
           }}
           style={{
             ...GLASS, padding: 30, textAlign: "center", cursor: "pointer",
             borderColor: drag ? GOLD : BORDER,
             background: drag ? "rgba(212,175,55,0.08)" : GLASS.background,
           }}
           onClick={() => document.getElementById("ora-file-input")?.click()}>
        <Upload size={28} color={GOLD} />
        <div style={{ fontSize: 14, fontWeight: 600, marginTop: 8 }}>
          {drag ? "Drop to upload" : "Drag-drop or click to upload"}
        </div>
        <div style={{ color: TEXT_DIM, fontSize: 11, marginTop: 4 }}>
          PDF · DOCX · TXT · MD · CSV · JSON · JPG/PNG · MP3 · MP4 — up to 30 MB
        </div>
        <input id="ora-file-input" type="file" multiple style={{ display: "none" }}
                onChange={(e) => upload(Array.from(e.target.files || []))} />
      </div>

      {(busy || error) && (
        <div style={{ ...GLASS, padding: 12, color: error ? RED : TEXT_DIM }}>
          {busy && <><Loader2 size={14} className="spin" /> Uploading…</>}
          {error && <><AlertTriangle size={14} /> {error}</>}
        </div>
      )}

      <div style={{ ...GLASS, padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
          <span style={{ color: TEXT_DIM, fontSize: 12, textTransform: "uppercase" }}>
            Uploaded files ({files.length})
          </span>
          <input data-testid="analyze-question" value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Question for ORA (optional)"
                  style={{
                    background: "rgba(0,0,0,0.4)", color: TEXT,
                    border: `1px solid ${BORDER}`, borderRadius: 8,
                    padding: "6px 10px", fontSize: 12, width: 320,
                  }} />
        </div>
        {files.length === 0 ? (
          <div style={{ color: TEXT_DIM, fontSize: 13, padding: 12 }}>No files yet.</div>
        ) : files.map((f) => (
          <FileRow key={f.id} f={f}
                    analyzing={analyzing === f.id}
                    analysis={analysis[f.id]}
                    onAnalyze={() => analyze(f.id)}
                    onDelete={() => remove(f.id)} />
        ))}
      </div>
      <style>{`.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function FileRow({ f, analyzing, analysis, onAnalyze, onDelete }) {
  const Icon = iconForMime(f.mime_type);
  return (
    <div data-testid={`file-row-${f.id}`}
         style={{ padding: 10, borderBottom: `1px solid rgba(212,175,55,0.06)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <Icon size={16} color={GOLD} />
        <div style={{ flex: 1, overflow: "hidden" }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{f.filename}</div>
          <div style={{ color: TEXT_DIM, fontSize: 11 }}>
            {f.mime_type} · {Math.round((f.size_bytes || 0) / 1024)} KB · {(f.ts || "").slice(0, 19)}
          </div>
        </div>
        <button data-testid={`analyze-${f.id}`} disabled={analyzing} onClick={onAnalyze} style={btn(true, analyzing)}>
          {analyzing ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />} Analyze with ORA
        </button>
        <button data-testid={`delete-${f.id}`} onClick={onDelete} style={btn(false)}>
          <Trash2 size={12} />
        </button>
      </div>
      {analysis && (
        <div style={{
          marginTop: 8, padding: 10, borderRadius: 8,
          background: "rgba(0,0,0,0.4)", border: `1px solid ${BORDER}`,
          fontSize: 12.5, whiteSpace: "pre-wrap",
          color: analysis.ok ? TEXT : RED,
        }}>
          {analysis.ok ? analysis.analysis : (analysis.error || "(no result)")}
        </div>
      )}
    </div>
  );
}

function iconForMime(mime) {
  if (!mime) return FileQuestion;
  if (mime.startsWith("image/")) return FileImage;
  if (mime.startsWith("audio/")) return FileAudio;
  if (mime.startsWith("video/")) return FileVideo;
  return FileText;
}

// ──────────────────────────────────────────────────────────────────────
// Style helpers
// ──────────────────────────────────────────────────────────────────────
const chatInput = {
  flex: 1, background: "rgba(0,0,0,0.4)", color: TEXT,
  border: `1px solid ${BORDER}`, borderRadius: 10,
  padding: "10px 14px", fontSize: 14,
};
const quickBtn = {
  padding: "10px 8px", fontSize: 12, fontWeight: 600,
  border: `1px solid ${BORDER}`, borderRadius: 10,
  cursor: "pointer", color: TEXT,
};
function btn(primary, disabled) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: primary ? GOLD : "rgba(255,255,255,0.06)",
    color: primary ? "#0A0A12" : TEXT,
    border: `1px solid ${primary ? GOLD : BORDER}`,
    borderRadius: 8, padding: "6px 12px", fontSize: 12,
    fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
  };
}
function tabBtn(active) {
  return {
    display: "flex", alignItems: "center", gap: 6,
    background: active ? GOLD : "rgba(255,255,255,0.04)",
    color: active ? "#0A0A12" : TEXT,
    border: `1px solid ${active ? GOLD : BORDER}`,
    borderRadius: 10, padding: "8px 14px", fontSize: 12.5,
    fontWeight: 700, cursor: "pointer", textTransform: "uppercase",
    letterSpacing: 0.3,
  };
}
