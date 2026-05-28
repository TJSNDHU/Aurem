/**
 * DevCtoChatPanel — iter 332b D-19 redesign
 *
 * Founder requests addressed:
 *   1. Full-screen chat surface (fills the dashboard viewport).
 *   2. Progress bar at the top during a build turn ([step N/M] markers
 *      from the model are parsed live; falls back to an indeterminate
 *      shimmer + token counter when no markers are present).
 *   3. Next-step chips below the input — parsed from the trailing
 *      `NEXT_STEPS:[...]` line the model is instructed to emit on every
 *      reply. Clicking a chip sends it as the next prompt.
 *   4. Persistent history — loaded from /api/developers/cto/chat/history
 *      on mount and persisted server-side on every completed stream.
 *      Refresh/logout never wipes a build session.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Send, Sparkles, AlertTriangle, Trash2, ArrowRight,
         Paperclip, Save, FileText, Image as ImageIcon,
         Copy, Check, Eye, Rocket, Undo2, X, Zap } from "lucide-react";
import SaveToGithubDialog from "./SaveToGithubDialog"; // iter D-47
import { devAuthHeaders, isMaxxOn } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";
const LOW_THRESHOLD = 100;

const WELCOME = {
  role: "assistant",
  content:
    "Hi — I'm AUREM CTO. Free tier is on, no setup needed.\n\n" +
    "Tell me what you want to build and I'll start with a numbered plan, " +
    "do the frontend first, then wire the backend. " +
    "Each step shows a progress bar so you can see what's done.\n\n" +
    "What are we building?",
};

// ─── Parsers for the model output contract ────────────────────────────
//
// [step N/M] markers → progress bar.
// NEXT_STEPS:[...]   → chip buttons.

const STEP_RE = /\[step\s+(\d+)\s*\/\s*(\d+)\]/gi;
const NEXTSTEPS_RE = /NEXT_STEPS:\s*(\[[\s\S]*?\])\s*$/i;

function parseProgress(text) {
  if (!text) return null;
  let last = null;
  let m;
  STEP_RE.lastIndex = 0;
  while ((m = STEP_RE.exec(text)) !== null) {
    last = { current: Number(m[1]), total: Number(m[2]) };
  }
  if (!last || !last.total || last.current > last.total) return null;
  return last;
}

function parseNextSteps(text) {
  if (!text) return [];
  const m = text.match(NEXTSTEPS_RE);
  if (!m) return [];
  try {
    const arr = JSON.parse(m[1]);
    if (Array.isArray(arr)) {
      return arr.filter(s => typeof s === "string" && s.trim())
                .slice(0, 4)
                .map(s => s.trim());
    }
  } catch { /* fallthrough */ }
  return [];
}

function stripContract(text) {
  // Hide the NEXT_STEPS:[...] tail line — we render it as chips instead.
  return (text || "").replace(NEXTSTEPS_RE, "").trimEnd();
}

function humanSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function Attachment({ att }) {
  if (!att) return null;
  const isImage = (att.mime || "").startsWith("image/");
  const Icon = isImage ? ImageIcon : FileText;
  return (
    <a href={att.url} target="_blank" rel="noopener noreferrer"
       data-testid="dev-cto-attachment-link"
       style={{ display: "inline-flex", alignItems: "center", gap: 8,
                marginTop: 6, padding: "8px 10px",
                background: "rgba(0,0,0,0.30)",
                border: "1px solid var(--dash-border)",
                borderRadius: 6, fontSize: 12,
                color: "#FFB070", textDecoration: "none",
                maxWidth: "100%" }}>
      <Icon size={14} />
      <span style={{ overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap" }}>
        {att.filename}
      </span>
      <span style={{ color: "var(--dash-text-faint)", fontSize: 10,
                      fontFamily: "'JetBrains Mono', monospace" }}>
        {humanSize(att.size)}
      </span>
    </a>
  );
}

// ─── Component ─────────────────────────────────────────────────────────

export default function DevCtoChatPanel({ onTokensUpdate, fullScreen = false,
                                          projectId = "", modelTier = "cheap" }) {
  const navigate = useNavigate();
  const location = useLocation();
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);   // iter D-33 — auto-grow textarea

  const [messages, setMessages] = useState([WELCOME]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [input, setInput]     = useState("");
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState(null);
  const [tier, setTier]       = useState("free");
  const [provider, setProvider] = useState("");
  const [showLowModal, setShowLowModal] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [streamChars, setStreamChars] = useState(0);

  // iter 332b D-20 — uploads in progress + save-project modal state.
  const [uploading, setUploading] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");
  const [saveDomain, setSaveDomain] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveOk, setSaveOk] = useState(null);
  // iter D-43 — planning bar dismiss + Maxx (frontier model) toggle.
  const [nextStepsDismissed, setNextStepsDismissed] = useState(false);
  const [maxx, setMaxx] = useState(isMaxxOn());
  // iter D-47 — Save-to-GitHub dialog state.
  const [showGithubSave, setShowGithubSave] = useState(false);

  // Load persisted history OR a saved project, depending on `?project=` query.
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams(location.search);
    const projectId = params.get("project");
    const url = projectId
      ? `${API}/api/developers/projects/${encodeURIComponent(projectId)}`
      : `${API}/api/developers/cto/chat/history`;
    fetch(url, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (cancelled) return;
        const past = Array.isArray(j?.messages) ? j.messages : [];
        if (past.length) setMessages([WELCOME, ...past]);
        setHistoryLoaded(true);
      })
      .catch(() => setHistoryLoaded(true));
    return () => { cancelled = true; };
  }, [location.search]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  // iter D-33 — auto-resize textarea up to 40vh, scroll INSIDE after.
  const autoResize = React.useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = Math.floor(window.innerHeight * 0.4);
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, []);
  useEffect(() => { autoResize(); }, [input, autoResize]);

  const lastAssistant = [...messages].reverse()
    .find(m => m.role === "assistant" && m.content);
  const nextSteps = busy ? [] : parseNextSteps(lastAssistant?.content || "");
  const progress = busy
    ? parseProgress(messages[messages.length - 1]?.content || "")
    : null;

  // iter D-43 — reset planning-bar dismiss + listen for sidebar Maxx
  // toggle so the chat composer + the button highlight stay in sync.
  useEffect(() => {
    setNextStepsDismissed(false);
  }, [lastAssistant?.id, lastAssistant?.content]);
  useEffect(() => {
    function onExt(e) {
      if (typeof e.detail?.on === "boolean") setMaxx(e.detail.on);
    }
    window.addEventListener("aurem-maxx-toggle", onExt);
    return () => window.removeEventListener("aurem-maxx-toggle", onExt);
  }, []);

  async function send(textOverride) {
    const text = (textOverride ?? input).trim();
    if (!text || busy) return;
    setError(null);
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setStreamChars(0);
    try {
      const history = next.slice(-12).map(m => ({
        role: m.role,
        content: String(m.content || "").slice(0, 3000),
      }));
      const r = await fetch(`${API}/api/developers/cto/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({
          messages: history,
          project_id: projectId || "",   // iter D-32 — debit wallet + patch progress
          // iter D-43 — Maxx toggle overrides incoming modelTier; flips
          // to frontier (5 tokens/turn) when on, else cheap (1/turn).
          model_tier: maxx ? "frontier" : (modelTier || "cheap"),
        }),
      });
      if (!r.ok) {
        const raw = await r.text();
        const friendly = r.status === 524
          ? "The free-tier model took too long. Please rephrase or try again."
          : (() => { try { return JSON.parse(raw).detail || JSON.parse(raw).message; }
                    catch { return `HTTP ${r.status}`; } })();
        throw new Error(friendly);
      }
      setMessages(m => [...m, { role: "assistant", content: "" }]);
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let receivedAny = false;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!chunk.startsWith("data:")) continue;
          let evt;
          try { evt = JSON.parse(chunk.slice(5).trim()); }
          catch { continue; }
          if (evt.type === "meta") {
            setTier(evt.tier || "free");
            setProvider(evt.provider || "");
            // iter D-47 — stamp provider/model onto the in-progress
            // assistant message so we can render a per-turn badge.
            const _meta = {
              provider: evt.provider || "",
              model:    evt.model    || "",
              tier:     evt.tier     || "",
            };
            setMessages(m => {
              const copy = m.slice();
              const last = copy[copy.length - 1];
              if (last && last.role === "assistant") {
                copy[copy.length - 1] = { ...last, meta: _meta };
              }
              return copy;
            });
          } else if (evt.type === "token") {
            receivedAny = true;
            setStreamChars(c => c + (evt.content?.length || 0));
            setMessages(m => {
              const copy = m.slice();
              const last = copy[copy.length - 1];
              if (last && last.role === "assistant") {
                copy[copy.length - 1] = {
                  ...last,
                  content: (last.content || "") + (evt.content || ""),
                };
              }
              return copy;
            });
          } else if (evt.type === "done") {
            if (typeof evt.tokens_remaining === "number") {
              onTokensUpdate?.(evt.tokens_remaining);
              if (evt.low_balance && !dismissed) setShowLowModal(true);
            }
          } else if (evt.type === "error") {
            // iter D-32 / D-33 — onboarding wallet ran out. Surface the
            // structured paywall instead of a plain text apology so the
            // customer sees the Builder/Pro upgrade option + the share-to-
            // earn shortcut in one place.
            if (evt.code === "insufficient_tokens") {
              setMessages(m => {
                const copy = m.slice();
                if (copy.length && copy[copy.length - 1].role === "assistant"
                    && !copy[copy.length - 1].content) {
                  copy.pop();
                }
                copy.push({
                  role: "assistant", warning: true,
                  paywall: {
                    balance: evt.balance || 0,
                    cost:    evt.cost || 1,
                  },
                  content: `You're out of build tokens — ${evt.balance || 0} left, this turn needs ${evt.cost || 1}.`,
                });
                return copy;
              });
              setShowLowModal(true);
              return;
            }
            if (evt.action_required === "add_byok") {
              setMessages(m => {
                const copy = m.slice();
                if (copy.length && copy[copy.length - 1].role === "assistant"
                    && !copy[copy.length - 1].content) {
                  copy.pop();
                }
                copy.push({
                  role: "assistant", warning: true,
                  content: evt.message ||
                    "You're out of free tokens. Add your own API key to keep going.",
                });
                return copy;
              });
              setShowLowModal(true);
            } else {
              throw new Error(evt.message || evt.error || "chat_failed");
            }
            return;
          }
        }
      }
      if (!receivedAny) throw new Error("No response received. Please try again.");
    } catch (e) {
      setMessages(m => {
        if (m.length && m[m.length - 1].role === "assistant"
            && !m[m.length - 1].content) {
          return m.slice(0, -1);
        }
        return m;
      });
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  async function clearHistory() {
    if (!window.confirm("Clear this chat? Server history will be wiped too.")) {
      return;
    }
    try {
      await fetch(`${API}/api/developers/cto/chat/history`, {
        method: "DELETE", headers: devAuthHeaders(),
      });
    } catch { /* ignore */ }
    setMessages([WELCOME]);
  }

  // iter 332b D-20 — upload a file. We POST the multipart, then push a
  // chat bubble with the attachment metadata. The model gets a textual
  // hint with the URL so it can reference the file in its next reply.
  async function handleFileSelect(e) {
    const f = e.target.files?.[0];
    e.target.value = "";  // allow re-uploading the same file
    if (!f) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", f);
      const r = await fetch(`${API}/api/developers/cto/uploads`, {
        method: "POST", body: form, headers: devAuthHeaders(),
      });
      if (!r.ok) {
        const t = await r.text();
        let detail = `HTTP ${r.status}`;
        try { detail = JSON.parse(t).detail || detail; } catch { /* */ }
        throw new Error(detail);
      }
      const j = await r.json();
      setMessages(m => [...m, {
        role: "user",
        content: `📎 Attached: ${j.filename} (${humanSize(j.size)})`,
        attachment: {
          file_id:  j.file_id,
          filename: j.filename,
          mime:     j.mime,
          size:     j.size,
          url:      `${API}${j.url}`,
        },
      }]);
    } catch (err) {
      setError(`Upload failed: ${err.message || err}`);
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveProject() {
    const title = saveTitle.trim();
    if (!title) {
      setSaveOk({ ok: false, msg: "Title is required." });
      return;
    }
    setSaveBusy(true);
    setSaveOk(null);
    try {
      const r = await fetch(`${API}/api/developers/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ title, domain: saveDomain.trim() || null }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error((() => { try { return JSON.parse(t).detail; }
                                  catch { return t; } })() || `HTTP ${r.status}`);
      }
      setSaveOk({ ok: true, msg: "Saved. Pinned to the sidebar." });
      window.dispatchEvent(new Event("dev-cto-project-saved"));
      setTimeout(() => {
        setShowSaveModal(false);
        setSaveTitle("");
        setSaveDomain("");
        setSaveOk(null);
      }, 900);
    } catch (err) {
      setSaveOk({ ok: false, msg: String(err.message || err) });
    } finally {
      setSaveBusy(false);
    }
  }

  // Full-screen layout fills the page; embedded mode keeps the legacy card.
  const wrapperStyle = fullScreen
    ? {
        display: "flex", flexDirection: "column",
        // Page header sits above this — give it ~120px of breathing room.
        height: "calc(100vh - 180px)",
        minHeight: 520,
        border: "1px solid rgba(255,107,0,0.18)",
        borderRadius: 6,
        background: "rgba(0,0,0,0.30)",
        overflow: "hidden",
      }
    : {
        marginBottom: 16, padding: 0, overflow: "hidden",
        border: "1px solid rgba(255,107,0,0.18)",
      };

  const listStyle = fullScreen
    ? { flex: 1, overflowY: "auto", padding: "16px 20px",
        background: "rgba(0,0,0,0.30)" }
    : { maxHeight: 360, minHeight: 240, overflowY: "auto",
        padding: "14px 18px", background: "rgba(0,0,0,0.30)" };

  return (
    <>
      <div data-testid="dev-cto-chat-panel"
           className={fullScreen ? "" : "av2-card"}
           style={wrapperStyle}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10,
                      padding: "12px 18px",
                      background: "linear-gradient(180deg, rgba(255,107,0,0.06), transparent)",
                      borderBottom: "1px solid var(--dash-divider)" }}>
          <Sparkles size={16} style={{ color: "#FF8C35" }} />
          <div style={{ flex: 1 }}>
            <div data-testid="dev-cto-chat-title"
                 style={{ fontSize: 14, fontWeight: 600,
                          color: "#F0EDE8" }}>
              AUREM CTO
            </div>
            <div data-testid="dev-cto-chat-tier"
                 style={{ fontSize: 10, color: "var(--dash-text-muted)",
                          letterSpacing: "0.15em", textTransform: "uppercase",
                          fontFamily: "'JetBrains Mono', monospace" }}>
              {tier === "byok"
                ? `BYOK · ${provider || "your key"} · 🌐 Live web`
                : "FREE TIER · OpenRouter · 🌐 Live web search"}
            </div>
          </div>
          {historyLoaded && (
            <>
              <button data-testid="dev-cto-chat-save"
                       onClick={() => setShowSaveModal(true)}
                       title="Save this build as a project"
                       style={{ background: "rgba(255,107,0,0.10)",
                                border: "1px solid rgba(255,107,0,0.30)",
                                color: "#FFB070",
                                borderRadius: 4, padding: "6px 10px",
                                fontSize: 11, cursor: "pointer",
                                display: "inline-flex", alignItems: "center",
                                gap: 6 }}>
                <Save size={12} /> Save project
              </button>
              <button data-testid="dev-cto-chat-clear"
                       onClick={clearHistory}
                       title="Clear chat history"
                       style={{ background: "transparent",
                                border: "1px solid var(--dash-border)",
                                color: "var(--dash-text-muted)",
                                borderRadius: 4, padding: "6px 10px",
                                fontSize: 11, cursor: "pointer",
                                display: "inline-flex", alignItems: "center",
                                gap: 6 }}>
                <Trash2 size={12} /> Clear
              </button>
            </>
          )}
        </div>

        {/* Progress bar — visible during a streaming turn */}
        {busy && (
          <ProgressBar progress={progress} chars={streamChars} />
        )}

        {/* iter D-43 — Planning bar at the top of chat. Replaces the
            bottom-of-input next-step chips. Shows "Planning the next
            move…" with three "+ <suggestion>" pills and a ✕ to dismiss
            the whole bar. */}
        {nextSteps.length > 0 && !nextStepsDismissed && (
          <div data-testid="dev-cto-planning-bar"
               style={{ display: "flex", alignItems: "center", gap: 8,
                        flexWrap: "wrap",
                        padding: "10px 18px",
                        borderBottom: "1px solid var(--dash-divider)",
                        background: "rgba(255,107,0,0.03)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8,
                           fontSize: 10, letterSpacing: "0.18em",
                           textTransform: "uppercase",
                           color: "var(--dash-text-muted)",
                           fontFamily: "'JetBrains Mono', monospace",
                           marginRight: 4 }}>
              <span data-testid="planning-dot"
                    style={{ width: 6, height: 6, borderRadius: 999,
                             background: busy ? "#FF8C35"
                                              : "var(--dash-text-faint)",
                             animation: busy
                               ? "aurem-pulse 1.2s ease-in-out infinite"
                               : "none" }} />
              Planning the next move…
            </div>
            {nextSteps.map((s, i) => (
              <button key={i}
                       data-testid={`dev-cto-planning-step-${i}`}
                       onClick={() => send(s)}
                       disabled={busy}
                       style={{ background: "rgba(255,107,0,0.08)",
                                border: "1px solid rgba(255,107,0,0.30)",
                                color: "#FFB070",
                                padding: "5px 10px 5px 8px",
                                borderRadius: 999,
                                fontSize: 12,
                                cursor: busy ? "not-allowed" : "pointer",
                                display: "inline-flex",
                                alignItems: "center", gap: 5 }}>
                <span style={{ width: 14, height: 14, borderRadius: 999,
                                background: "rgba(255,107,0,0.20)",
                                display: "inline-flex",
                                alignItems: "center", justifyContent: "center",
                                fontWeight: 700, fontSize: 11 }}>+</span>
                {s}
              </button>
            ))}
            <button data-testid="dev-cto-planning-dismiss"
                     onClick={() => setNextStepsDismissed(true)}
                     title="Dismiss"
                     style={{ marginLeft: "auto",
                              background: "transparent",
                              border: "none",
                              color: "var(--dash-text-faint)",
                              cursor: "pointer", padding: 4,
                              display: "inline-flex", alignItems: "center" }}>
              <X size={13} />
            </button>
          </div>
        )}

        {/* Message list */}
        <div ref={scrollRef}
             data-testid="dev-cto-chat-messages"
             style={listStyle}>
          {messages.map((m, i) => {
            const displayed = m.role === "assistant"
              ? stripContract(m.content)
              : m.content;
            if (m.role === "assistant" && !displayed && !busy) return null;
            return (
              <div key={i}
                   data-testid={m.role === "user"
                     ? "dev-cto-msg-user" : "dev-cto-msg-assistant"}
                   className={m.role === "assistant" ? "dev-cto-msg-bubble" : ""}
                   style={{ marginBottom: 14,
                            display: "flex",
                            flexDirection: m.role === "user" ? "row-reverse" : "row" }}>
                <div style={{ maxWidth: "82%",
                              padding: "10px 14px", borderRadius: 6,
                              fontSize: 13, lineHeight: 1.55,
                              whiteSpace: "pre-wrap",
                              position: "relative",
                              background: m.role === "user"
                                ? "rgba(255,107,0,0.12)"
                                : m.warning
                                  ? "rgba(255,179,107,0.10)"
                                  : "rgba(255,255,255,0.04)",
                              color: m.warning ? "#FFD194" : "#F0EDE8",
                              border: m.warning
                                ? "1px solid rgba(255,179,107,0.30)"
                                : "1px solid rgba(255,255,255,0.06)" }}>
                  {displayed || (busy && m.role === "assistant" ? "…" : "")}
                  {m.attachment && <Attachment att={m.attachment} />}
                  {m.paywall && <PaywallBlock info={m.paywall} />}
                  {/* iter D-47 — per-turn model badge. Only on
                      assistant bubbles that received a meta event. */}
                  {m.role === "assistant" && m.meta && (m.meta.provider || m.meta.model) && (
                    <span data-testid={`dev-cto-msg-model-badge-${i}`}
                          title={m.meta.model
                            ? `${m.meta.provider || ""} · ${m.meta.model}`
                            : m.meta.provider}
                          style={{ display: "inline-flex",
                                   alignItems: "center", gap: 4,
                                   marginTop: 8, padding: "2px 7px",
                                   borderRadius: 999,
                                   background: m.meta.tier === "byok"
                                     ? "rgba(232,200,106,0.10)"
                                     : "rgba(255,140,53,0.10)",
                                   border: m.meta.tier === "byok"
                                     ? "1px solid rgba(232,200,106,0.30)"
                                     : "1px solid rgba(255,140,53,0.30)",
                                   color: m.meta.tier === "byok"
                                     ? "#E8C86A" : "#FF8C35",
                                   fontFamily: "'JetBrains Mono', monospace",
                                   fontSize: 9.5,
                                   letterSpacing: 0.3 }}>
                      {(m.meta.provider || m.meta.model || "").toLowerCase()}
                    </span>
                  )}
                  {m.role === "assistant" && displayed && !busy && (
                    <BubbleActionRow text={displayed}
                                      index={i}
                                      messageId={m.id}
                                      projectId={projectId} />
                  )}
                </div>
              </div>
            );
          })}
          {error && (
            <div data-testid="dev-cto-chat-error"
                 style={{ fontSize: 12, color: "#FF6060",
                          padding: 8, marginTop: 8,
                          background: "rgba(255,96,96,0.08)",
                          border: "1px solid rgba(255,96,96,0.25)",
                          borderRadius: 4 }}>
              {error}
            </div>
          )}
        </div>

        {/* iter D-43 — bottom NEXT_STEPS chips removed; they're rendered
            as the Planning bar at the top of the chat panel above. */}

        {/* iter D-38 — chat footer actions bar (Preview + Deploy moved
            here so they no longer cover the in-bubble Copy/Rollback
            buttons on hover). Shows only when a project is loaded. */}
        {projectId && (
          <ChatFooterActions projectId={projectId} busy={busy} />
        )}

        {/* Input */}
        <div style={{ display: "flex", gap: 10, padding: "12px 18px",
                      borderTop: "1px solid var(--dash-divider)",
                      background: "rgba(0,0,0,0.20)" }}>
          {/* iter 332b D-20 — upload button. Hidden native input
              triggered by the visible icon button. */}
          <input ref={fileInputRef}
                  type="file"
                  data-testid="dev-cto-chat-file-input"
                  onChange={handleFileSelect}
                  style={{ display: "none" }} />
          <button data-testid="dev-cto-chat-upload"
                   onClick={() => fileInputRef.current?.click()}
                   disabled={uploading || busy}
                   title="Attach a file (max 25 MB)"
                   style={{ background: "rgba(255,255,255,0.04)",
                            border: "1px solid var(--dash-border)",
                            color: uploading
                              ? "var(--dash-orange)"
                              : "var(--dash-text-muted)",
                            borderRadius: 4, padding: "0 12px",
                            cursor: uploading ? "not-allowed" : "pointer",
                            display: "flex", alignItems: "center" }}>
            <Paperclip size={14} />
          </button>
          <textarea ref={textareaRef}
                     data-testid="dev-cto-chat-input"
                     value={input}
                     onChange={e => {
                       setInput(e.target.value);
                       autoResize();
                     }}
                     onKeyDown={onKey}
                     placeholder="Tell AUREM CTO what to build — frontend first, then backend. Type /search <query> or include a URL to use live web search."
                     rows={1}
                     style={{ flex: 1, background: "rgba(255,255,255,0.04)",
                              border: "1px solid var(--dash-border)",
                              color: "#F0EDE8", padding: "10px 12px",
                              borderRadius: 4, fontSize: 13,
                              fontFamily: "inherit", outline: "none",
                              resize: "none",
                              minHeight: 40,
                              maxHeight: "40vh",
                              overflowY: "auto",
                              transition: "height 80ms ease" }} />
          {/* iter D-43 — Maxx toggle (frontier model, 5/turn). Mirrors
              the sidebar Maxx button so the dev can flip it without
              moving their hand off the composer. */}
          <button data-testid="dev-cto-chat-maxx"
                   onClick={() => {
                     const next = !maxx;
                     try { localStorage.setItem("aurem.maxx_mode",
                                                  next ? "1" : "0"); }
                     catch { /* ignore */ }
                     setMaxx(next);
                     window.dispatchEvent(new CustomEvent(
                       "aurem-maxx-toggle", { detail: { on: next } }));
                   }}
                   title={maxx ? "Maxx ON — frontier model, 5 tokens/turn"
                               : "Maxx OFF — cheap model, 1 token/turn"}
                   style={{ background: maxx
                              ? "linear-gradient(135deg, rgba(255,107,0,0.22), rgba(255,140,53,0.14))"
                              : "rgba(255,255,255,0.04)",
                            border: maxx
                              ? "1px solid rgba(255,107,0,0.45)"
                              : "1px solid var(--dash-border)",
                            color: maxx ? "#FF8C35"
                                        : "var(--dash-text-muted)",
                            borderRadius: 4, padding: "0 12px",
                            cursor: "pointer",
                            display: "flex", alignItems: "center", gap: 4,
                            fontSize: 11, fontWeight: 500,
                            transition: "all 160ms ease" }}>
            <Zap size={13} />
            {maxx ? "Maxx" : ""}
          </button>
          {/* iter D-47 — Save to GitHub button (next to Maxx). Disabled
              until a project is loaded so the dialog has somewhere to
              save to. */}
          <button data-testid="dev-cto-chat-save-github"
                   onClick={() => setShowGithubSave(true)}
                   disabled={busy || !projectId}
                   title={projectId
                     ? "Commit manifest + chat history to a GitHub repo"
                     : "Save the project first, then commit to GitHub"}
                   style={{ background: "#24292F",
                            border: "1px solid #1B1F23",
                            color: "#fff", borderRadius: 4,
                            padding: "0 12px",
                            cursor: (busy || !projectId)
                              ? "not-allowed" : "pointer",
                            opacity: (busy || !projectId) ? 0.5 : 1,
                            display: "flex", alignItems: "center", gap: 5,
                            fontSize: 11, fontWeight: 500 }}>
            <Save size={13} /> Github
          </button>
          <button data-testid="dev-cto-chat-send"
                   onClick={() => send()} disabled={busy || !input.trim()}
                   style={{ background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                            color: "#fff", border: "none", borderRadius: 4,
                            padding: "0 18px", fontSize: 13, fontWeight: 500,
                            cursor: busy ? "not-allowed" : "pointer",
                            opacity: busy ? 0.5 : 1,
                            display: "flex", alignItems: "center", gap: 6 }}>
            <Send size={14} /> Send
          </button>
        </div>
      </div>

      {/* iter 332b D-20 — Save-as-project modal */}
      {showSaveModal && (
        <div data-testid="dev-cto-save-modal"
             style={{ position: "fixed", inset: 0,
                      background: "rgba(0,0,0,0.78)",
                      display: "flex", alignItems: "center",
                      justifyContent: "center", zIndex: 9999,
                      padding: 20 }}>
          <div style={{ maxWidth: 460, width: "100%",
                        background: "#0F0F1A",
                        border: "1px solid rgba(255,107,0,0.45)",
                        borderRadius: 8, padding: 26 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10,
                          marginBottom: 16 }}>
              <Save size={20} style={{ color: "#FF8C35" }} />
              <h2 style={{ fontSize: 17, fontWeight: 600,
                            color: "#F0EDE8", margin: 0,
                            fontFamily: "'Cinzel', serif" }}>
                Save this build
              </h2>
            </div>
            <p style={{ fontSize: 12, color: "var(--dash-text-muted)",
                        lineHeight: 1.6, marginBottom: 14 }}>
              We'll snapshot the conversation and pin it to your sidebar
              so you can come back to it anytime — even after a logout.
            </p>
            <label style={{ fontSize: 10, letterSpacing: "0.18em",
                              textTransform: "uppercase",
                              color: "var(--dash-text-muted)" }}>
              Project title
            </label>
            <input data-testid="dev-cto-save-title"
                    value={saveTitle}
                    onChange={e => setSaveTitle(e.target.value)}
                    placeholder="e.g. Internal admin dashboard v1"
                    autoFocus
                    style={{ width: "100%", marginTop: 4, marginBottom: 12,
                              background: "rgba(255,255,255,0.04)",
                              border: "1px solid var(--dash-border)",
                              color: "#F0EDE8", padding: "9px 11px",
                              borderRadius: 4, fontSize: 13,
                              fontFamily: "inherit", outline: "none",
                              boxSizing: "border-box" }} />
            <label style={{ fontSize: 10, letterSpacing: "0.18em",
                              textTransform: "uppercase",
                              color: "var(--dash-text-muted)" }}>
              Domain (optional)
            </label>
            <input data-testid="dev-cto-save-domain"
                    value={saveDomain}
                    onChange={e => setSaveDomain(e.target.value)}
                    placeholder="e.g. admin.acme.com"
                    style={{ width: "100%", marginTop: 4, marginBottom: 18,
                              background: "rgba(255,255,255,0.04)",
                              border: "1px solid var(--dash-border)",
                              color: "#F0EDE8", padding: "9px 11px",
                              borderRadius: 4, fontSize: 13,
                              fontFamily: "'JetBrains Mono', monospace",
                              outline: "none",
                              boxSizing: "border-box" }} />
            {saveOk && (
              <div data-testid="dev-cto-save-status"
                   style={{ fontSize: 12,
                            color: saveOk.ok ? "var(--dash-green)" : "#FF6060",
                            marginBottom: 12 }}>
                {saveOk.msg}
              </div>
            )}
            <div style={{ display: "flex", gap: 10 }}>
              <button data-testid="dev-cto-save-confirm"
                       onClick={handleSaveProject}
                       disabled={saveBusy || !saveTitle.trim()}
                       style={{ flex: 1, padding: "10px 18px",
                                background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                                color: "#fff", border: "none", borderRadius: 4,
                                fontSize: 13, fontWeight: 500,
                                cursor: saveBusy ? "not-allowed" : "pointer",
                                opacity: saveBusy ? 0.5 : 1 }}>
                {saveBusy ? "Saving…" : "Save project"}
              </button>
              <button data-testid="dev-cto-save-cancel"
                       onClick={() => { setShowSaveModal(false); setSaveOk(null); }}
                       disabled={saveBusy}
                       style={{ padding: "10px 18px",
                                background: "transparent",
                                border: "1px solid var(--dash-border)",
                                color: "var(--dash-text-muted)",
                                borderRadius: 4, fontSize: 13,
                                cursor: "pointer" }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* iter D-47 — Save-to-GitHub dialog. */}
      <SaveToGithubDialog open={showGithubSave}
                            projectId={projectId}
                            onClose={() => setShowGithubSave(false)} />

      {/* Token-low modal — unchanged */}
      {showLowModal && (
        <div data-testid="dev-cto-low-tokens-modal"
             style={{ position: "fixed", inset: 0,
                      background: "rgba(0,0,0,0.78)",
                      display: "flex", alignItems: "center",
                      justifyContent: "center", zIndex: 9999,
                      padding: 20 }}>
          <div style={{ maxWidth: 480, width: "100%",
                        background: "#0F0F1A",
                        border: "1px solid rgba(255,107,0,0.45)",
                        borderRadius: 8, padding: 26 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10,
                          marginBottom: 14 }}>
              <AlertTriangle size={22} style={{ color: "#FF8C35" }} />
              <h2 data-testid="dev-cto-low-tokens-title"
                  style={{ fontSize: 18, fontWeight: 600,
                           color: "#F0EDE8", margin: 0,
                           fontFamily: "'Cinzel', serif" }}>
                Running low — add a DeepSeek key
              </h2>
            </div>
            <p style={{ fontSize: 13, color: "var(--dash-text-muted)",
                        lineHeight: 1.6, marginBottom: 18 }}>
              Your free tokens are almost gone. Add your own DeepSeek API
              key for <strong style={{ color: "#FF8C35" }}>98% cheaper
              tokens</strong> ($0.27 per million) and never hit a wall again.
              Takes 60 seconds.
            </p>
            <div style={{ display: "flex", gap: 10 }}>
              <button data-testid="dev-cto-low-tokens-cta"
                       onClick={() => navigate("/developers/connect")}
                       style={{ flex: 1, padding: "10px 18px",
                                background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                                color: "#fff", border: "none", borderRadius: 4,
                                fontSize: 13, fontWeight: 500, cursor: "pointer" }}>
                Add my DeepSeek key →
              </button>
              <button data-testid="dev-cto-low-tokens-dismiss"
                       onClick={() => { setShowLowModal(false); setDismissed(true); }}
                       style={{ padding: "10px 18px",
                                background: "transparent",
                                border: "1px solid var(--dash-border)",
                                color: "var(--dash-text-muted)",
                                borderRadius: 4, fontSize: 13,
                                cursor: "pointer" }}>
                Later
              </button>
            </div>
            <div style={{ fontSize: 10, color: "var(--dash-text-faint)",
                          marginTop: 14, textAlign: "center",
                          fontFamily: "'JetBrains Mono', monospace",
                          letterSpacing: "0.1em" }}>
              THRESHOLD: {LOW_THRESHOLD} TOKENS
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Progress bar ──────────────────────────────────────────────────────
function ProgressBar({ progress, chars }) {
  const pct = progress
    ? Math.min(100, Math.round((progress.current / progress.total) * 100))
    : null;
  const label = progress
    ? `Step ${progress.current} of ${progress.total}`
    : chars > 0
      ? `Generating — ${chars.toLocaleString()} chars`
      : "Thinking…";
  return (
    <div data-testid="dev-cto-chat-progress"
         style={{ padding: "8px 18px",
                  borderBottom: "1px solid var(--dash-divider)",
                  background: "rgba(255,107,0,0.04)" }}>
      <div style={{ display: "flex", justifyContent: "space-between",
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 10, letterSpacing: "0.18em",
                    textTransform: "uppercase",
                    color: "var(--dash-text-muted)", marginBottom: 6 }}>
        <span data-testid="dev-cto-progress-label">{label}</span>
        <span data-testid="dev-cto-progress-pct">
          {pct !== null ? `${pct}%` : ""}
        </span>
      </div>
      <div style={{ height: 4, borderRadius: 2,
                    background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        {pct !== null ? (
          <div style={{ height: "100%", width: `${pct}%`,
                        background: "linear-gradient(90deg, #FF6B00, #FF8C35)",
                        transition: "width 250ms ease" }} />
        ) : (
          <div style={{ height: "100%", width: "30%",
                        background: "linear-gradient(90deg, #FF6B00, #FF8C35)",
                        animation: "dev-cto-shimmer 1.4s ease-in-out infinite" }} />
        )}
      </div>
      <style>{`
        @keyframes dev-cto-shimmer {
          0% { margin-left: -30%; }
          100% { margin-left: 100%; }
        }
      `}</style>
    </div>
  );
}


// ─── Copy-to-clipboard button on assistant messages (P2 D-30) ─────────
function CopyMessageButton({ text, index }) {
  const [copied, setCopied] = React.useState(false);
  const onClick = React.useCallback(async () => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }, [text]);
  return (
    <button
      data-testid={`dev-cto-copy-btn-${index}`}
      onClick={onClick}
      aria-label={copied ? "Copied" : "Copy message"}
      title={copied ? "Copied" : "Copy message"}
      style={{
        position: "absolute",
        right: 6, bottom: 6,
        width: 26, height: 26,
        display: "inline-flex",
        alignItems: "center", justifyContent: "center",
        background: copied
          ? "rgba(80,200,120,0.12)"
          : "rgba(255,255,255,0.05)",
        border: copied
          ? "1px solid rgba(80,200,120,0.45)"
          : "1px solid rgba(255,255,255,0.10)",
        borderRadius: 4,
        color: copied ? "#50C878" : "#9CA3AF",
        cursor: "pointer",
        transition: "all 140ms ease",
        opacity: 0.85,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = "1"; }}
      onMouseLeave={(e) => { e.currentTarget.style.opacity = "0.85"; }}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  );
}

// ─── Paywall block (iter D-33) ───────────────────────────────────────
// Renders inside the assistant bubble when the backend returns the
// `insufficient_tokens` SSE error. Existing Stripe Builder/Pro tiers
// already live at /pricing; this is a UI gate only — no new Stripe
// integration. Share-to-earn shortcut routes back to /my/projects/new
// where the existing ShareForTokensCard lives.
function PaywallBlock({ info }) {
  const balance = info?.balance ?? 0;
  const cost    = info?.cost    ?? 1;
  return (
    <div data-testid="paywall-block"
         style={{ marginTop: 12, padding: 14, borderRadius: 6,
                   background: "rgba(255,107,0,0.08)",
                   border: "1px solid rgba(255,107,0,0.35)" }}>
      <div style={{ fontSize: 11, letterSpacing: "0.15em",
                     textTransform: "uppercase",
                     color: "#FF8C35", marginBottom: 6 }}>
        Tokens — {balance} left · this turn needs {cost}
      </div>
      <div style={{ fontSize: 13, color: "#F0EDE8",
                     marginBottom: 12 }}>
        Two ways to keep building right now:
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <a data-testid="paywall-upgrade-btn"
           href="/pricing"
           style={{ display: "inline-flex", alignItems: "center", gap: 6,
                     padding: "10px 18px",
                     background: "linear-gradient(135deg, #FF6B00, #FF8C35)",
                     color: "#fff", textDecoration: "none",
                     border: "none", borderRadius: 6,
                     fontSize: 13, fontWeight: 500 }}>
          Upgrade to Builder or Pro
        </a>
        <a data-testid="paywall-share-btn"
           href="/my/projects/new#share"
           style={{ display: "inline-flex", alignItems: "center", gap: 6,
                     padding: "10px 16px",
                     background: "transparent",
                     border: "1px solid rgba(201,168,76,0.45)",
                     color: "#C9A84C", borderRadius: 6,
                     fontSize: 13, fontWeight: 500,
                     textDecoration: "none" }}>
          Share AUREM → +2500 free tokens
        </a>
      </div>
      <div style={{ marginTop: 10, fontSize: 11,
                     color: "rgba(240,237,232,0.55)" }}>
        Builder gets 50,000 tokens / month + priority frontier models. Pro
        is unlimited cheap-tier + 200k frontier tokens.
      </div>
    </div>
  );
}


// ─── iter D-33: hover-reveal Preview + Deploy buttons ────────────────
// We surface them only when the assistant reply contains the literal
// markers we already emit for builds (fenced code blocks, MANIFEST_PATCH,
// or "[step N/M]"). The buttons sit at the BUBBLE bottom-right and fade
// in on hover via the `.dev-cto-msg-bubble:hover .dev-cto-msg-actions`
// CSS rule injected at the end of the panel.

// iter D-38 — Bubble action row.
// Sits at the bottom-right of every assistant bubble. Replaces the
// hover-only Preview/Deploy reveal that used to overlap the Copy
// button. Two buttons that ALWAYS render (no hover dependency):
//   • Copy  — clipboard
//   • Rollback — restores the project to the snapshot taken right
//                BEFORE this assistant turn (best-effort; opens the
//                Connect page when no snapshot exists yet).
// Preview + Deploy moved to ChatFooterActions below the chat stream.
function BubbleActionRow({ text, index, messageId, projectId }) {
  const [copied,  setCopied]  = React.useState(false);
  const [rolling, setRolling] = React.useState(false);

  async function copy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        document.execCommand("copy"); document.body.removeChild(ta);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch { setCopied(false); }
  }

  async function rollback() {
    if (!projectId) {
      window.location.href = "/developers/connect#deploy";
      return;
    }
    if (!window.confirm("Rollback to the state BEFORE this AUREM CTO reply?\nYour project will revert to the previous snapshot.")) {
      return;
    }
    setRolling(true);
    try {
      const r = await fetch(`${API}/api/developers/deploy/run`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body:    JSON.stringify({ mode: "rollback",
                                    message_id: messageId || String(index),
                                    project_id: projectId }),
      });
      const j = await r.json();
      if (r.status === 400 && j.detail === "deploy_not_configured") {
        window.location.href = "/developers/connect#deploy";
        return;
      }
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "rollback_failed");
      window.location.href = `/developers/connect#deploy-${j.run_id || ""}`;
    } catch (e) {
      window.alert(`Rollback failed: ${e.message || e}.`);
    } finally {
      setRolling(false);
    }
  }

  return (
    <div className="dev-cto-bubble-actions"
         data-testid={`dev-cto-bubble-actions-${index}`}
         style={{ position: "absolute", right: 6, bottom: 6,
                   display: "inline-flex", gap: 4 }}>
      <button data-testid={`dev-cto-copy-btn-${index}`}
              onClick={copy}
              aria-label={copied ? "Copied" : "Copy message"}
              title={copied ? "Copied" : "Copy message"}
              style={bubbleBtnStyle(copied
                ? { fg: "#50C878", bg: "rgba(80,200,120,0.12)",
                    bd: "rgba(80,200,120,0.45)" }
                : { fg: "#9CA3AF", bg: "rgba(255,255,255,0.05)",
                    bd: "rgba(255,255,255,0.10)" })}>
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
      <button data-testid={`dev-cto-rollback-btn-${index}`}
              onClick={rollback}
              disabled={rolling}
              aria-label="Rollback to before this reply"
              title="Rollback this build to the snapshot taken before this reply"
              style={bubbleBtnStyle({
                fg: rolling ? "#666" : "#FFB36B",
                bg: "rgba(255,140,53,0.07)",
                bd: "rgba(255,140,53,0.30)",
              })}>
        <Undo2 size={12} />
      </button>
    </div>
  );
}

function bubbleBtnStyle({ fg, bg, bd }) {
  return {
    width: 26, height: 26,
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    background: bg, border: `1px solid ${bd}`, borderRadius: 4,
    color: fg, cursor: "pointer",
    transition: "all 140ms cubic-bezier(0.23, 1, 0.32, 1)",
    opacity: 0.9,
  };
}

// iter D-38 — Chat footer actions (Preview + Deploy).
// Sits BETWEEN the next-steps chip row and the input box. Replaces the
// hover-only buttons that used to live INSIDE assistant bubbles and
// covered the Copy/Rollback controls.
function ChatFooterActions({ projectId, busy }) {
  const [deploying, setDeploying] = React.useState(false);
  const preview = `https://preview.aurem.live/${projectId}`;

  async function deploy() {
    if (!window.confirm("Deploy the latest changes to your project?")) return;
    setDeploying(true);
    try {
      const r = await fetch(`${API}/api/developers/deploy/run`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body:    JSON.stringify({ mode: "deploy", project_id: projectId }),
      });
      const j = await r.json();
      if (r.status === 400 && j.detail === "deploy_not_configured") {
        window.location.href = "/developers/connect#deploy";
        return;
      }
      if (r.status === 409) {
        // D-35 production-dogfood guard
        window.alert("Run a successful dry-run first — production protection is active.");
        return;
      }
      if (!r.ok) throw new Error(j.detail?.msg || j.detail || "deploy_failed");
      window.location.href = `/developers/connect#deploy-${j.run_id || ""}`;
    } catch (e) {
      window.alert(`Deploy failed: ${e.message || e}. Open the Connect page to configure your deploy target.`);
    } finally {
      setDeploying(false);
    }
  }

  return (
    <div className="dev-cto-footer-actions"
         data-testid="dev-cto-chat-footer-actions"
         style={{ display: "flex", gap: 8,
                    padding: "10px 18px",
                    borderTop: "1px solid var(--dash-divider)",
                    background: "rgba(0,0,0,0.12)",
                    flexWrap: "wrap" }}>
      <span style={{ fontSize: 9, letterSpacing: "0.18em",
                      textTransform: "uppercase",
                      color: "var(--dash-text-muted)",
                      fontFamily: "'JetBrains Mono', monospace",
                      padding: "6px 4px" }}>
        Project:
      </span>
      <a data-testid="dev-cto-footer-preview-btn"
         href={preview} target="_blank" rel="noreferrer"
         title="Open the live preview in a new tab"
         style={footerBtnStyle("preview", busy)}>
        <Eye size={12} /> Preview
      </a>
      <button data-testid="dev-cto-footer-deploy-btn"
              onClick={deploy}
              disabled={busy || deploying}
              title="Deploy the latest changes to your server"
              style={footerBtnStyle("deploy", busy || deploying)}>
        <Rocket size={12} /> {deploying ? "Deploying…" : "Deploy"}
      </button>
    </div>
  );
}

function footerBtnStyle(kind, disabled) {
  const accent = kind === "deploy" ? "#50C878" : "#FF8C35";
  return {
    display: "inline-flex", alignItems: "center", gap: 6,
    padding: "7px 14px",
    background: `${accent}14`,
    border: `1px solid ${accent}55`,
    color: accent, borderRadius: 4,
    fontSize: 12, fontWeight: 500,
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: "0.05em", textDecoration: "none",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.5 : 1,
    transition: "all 140ms cubic-bezier(0.23, 1, 0.32, 1)",
  };
}

function containsCodeChange(text) {
  if (!text) return false;
  if (text.includes("```")) return true;
  if (/\bMANIFEST_PATCH\s*:/i.test(text)) return true;
  if (/\[step\s+\d+\/\d+\]/i.test(text)) return true;
  return false;
}

function _unused_legacy_MessageActionButtons({ index, projectId }) {
  // Kept here as a no-op stub so any external import doesn't crash.
  // The real footer-based Preview/Deploy lives in ChatFooterActions.
  return null;
}

function actionBtnStyle(kind) {
  const accent = kind === "deploy" ? "#50C878" : "#FF8C35";
  return {
    display: "inline-flex", alignItems: "center", gap: 4,
    padding: "4px 9px",
    background: "rgba(0,0,0,0.55)",
    border: `1px solid ${accent}40`,
    color: accent, borderRadius: 4,
    fontSize: 10, fontWeight: 500,
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: "0.05em",
    textDecoration: "none",
    cursor: "pointer",
    backdropFilter: "blur(6px)",
  };
}

// Inject the hover CSS rule once at module load.
if (typeof document !== "undefined"
    && !document.getElementById("dev-cto-msg-actions-css")) {
  const s = document.createElement("style");
  s.id = "dev-cto-msg-actions-css";
  s.textContent = `
    .dev-cto-msg-bubble:hover .dev-cto-msg-actions {
      opacity: 1 !important;
      pointer-events: auto !important;
    }
    /* Touch devices have no hover — show always */
    @media (hover: none) {
      .dev-cto-msg-actions {
        opacity: 1 !important;
        pointer-events: auto !important;
      }
    }
  `;
  document.head.appendChild(s);
}

