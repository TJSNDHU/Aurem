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
  RotateCcw,
} from "lucide-react";

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

export default function OraChat() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("chat");
  return (
    <div data-testid="ora-chat" style={{ minHeight: "100vh", background: "#0A0A12", color: TEXT, padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
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

      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
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

      {tab === "chat"  && <ChatPane />}
      {tab === "cto"   && <CTOPane />}
      {tab === "files" && <FilesPane />}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────
// Tab 1 — General Chat
// ──────────────────────────────────────────────────────────────────────
function ChatPane() {
  const [history, setHistory] = useState([]);  // {role, content, provider?, ms?}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId] = useState(() => `ora-chat-${Date.now().toString(36)}`);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history, busy]);

  const send = async () => {
    const q = input.trim();
    if (!q || busy) return;
    setHistory((h) => [...h, { role: "user", content: q }]);
    setInput("");
    setBusy(true);
    try {
      const t0 = Date.now();
      const r = await fetch(`${API}/api/public/ora/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ text: q, session_id: sessionId }),
      });
      const j = await r.json();
      setHistory((h) => [...h, {
        role: "assistant",
        content: j.reply || j.detail || JSON.stringify(j),
        provider: j.provider,
        ms: Date.now() - t0,
      }]);
    } catch (e) {
      setHistory((h) => [...h, { role: "error", content: String(e) }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ ...GLASS, padding: 16, display: "grid", gridTemplateRows: "1fr auto", gap: 12, minHeight: 600 }}>
      <div ref={scrollRef} style={{ overflowY: "auto", maxHeight: 540, paddingRight: 6 }}>
        {history.length === 0 && (
          <div style={{ color: TEXT_DIM, fontSize: 13, padding: 24, textAlign: "center" }}>
            <Sparkles size={28} color={GOLD} /> <br />
            Talk to ORA. She has access to AUREM's full skill library + Sovereign Node fallbacks.
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
            }}>
              <div style={{ color: TEXT_DIM, fontSize: 10, marginBottom: 4,
                              textTransform: "uppercase" }}>
                {m.role === "user" ? "you" : m.role === "error" ? "error" : "ORA"}
                {m.provider && <span style={{ marginLeft: 6 }}>· {m.provider}</span>}
                {m.ms && <span style={{ marginLeft: 6 }}>· {m.ms}ms</span>}
              </div>
              <div style={{ fontSize: 13.5, whiteSpace: "pre-wrap" }}>{m.content}</div>
            </div>
          </div>
        ))}
        {busy && (
          <div style={{ color: TEXT_DIM, fontSize: 12 }}>
            <Loader2 size={14} className="spin" /> ORA is thinking…
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
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
  const navigate = useNavigate();

  const loadRecent = async () => {
    try {
      const r = await fetch(`${API}/api/ora-tools/invocations?limit=10`,
                             { headers: authHeaders() });
      const j = await r.json();
      if (j?.ok) setRecent(j.invocations || []);
    } catch { /* soft fail */ }
  };
  const loadBackups = async () => {
    try {
      const r = await fetch(`${API}/api/admin/ora-rollback/list?limit=10`,
                             { headers: authHeaders() });
      const j = await r.json();
      if (j?.ok) setBackups(j.rows || []);
    } catch { /* soft fail */ }
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
      const j = await r.json();
      setResult(j);
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
      }).then(r => r.json());
      steps.push({ step: "lint_python", ok: linted.ok, summary: linted.error_count ?? linted.error });
      const restarted = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: "restart_service", args: { service: "backend" } }),
      }).then(r => r.json());
      steps.push({ step: "restart_service", ok: restarted.ok });
      // Wait a tick for the supervisor to bring things back
      await new Promise((res) => setTimeout(res, 4000));
      const hc = await fetch(`${API}/api/ora-tools/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tool: "health_check", args: {} }),
      }).then(r => r.json());
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
      const j = await r.json();
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
      const j = await r.json();
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
      const j = await r.json();
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
        const j = await r.json();
        if (!r.ok) setError(j.detail || `upload failed for ${f.name}`);
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
      const j = await r.json();
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
