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
import { useNavigate } from "react-router-dom";
import { Send, Sparkles, AlertTriangle, Trash2, ArrowRight } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

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

// ─── Component ─────────────────────────────────────────────────────────

export default function DevCtoChatPanel({ onTokensUpdate, fullScreen = false }) {
  const navigate = useNavigate();
  const scrollRef = useRef(null);

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

  // Load persisted history once on mount.
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/api/developers/cto/chat/history`, { headers: devAuthHeaders() })
      .then(r => r.ok ? r.json() : null)
      .then(j => {
        if (cancelled) return;
        const past = Array.isArray(j?.messages) ? j.messages : [];
        if (past.length) setMessages([WELCOME, ...past]);
        setHistoryLoaded(true);
      })
      .catch(() => setHistoryLoaded(true));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  const lastAssistant = [...messages].reverse()
    .find(m => m.role === "assistant" && m.content);
  const nextSteps = busy ? [] : parseNextSteps(lastAssistant?.content || "");
  const progress = busy
    ? parseProgress(messages[messages.length - 1]?.content || "")
    : null;

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
        body: JSON.stringify({ messages: history }),
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
                ? `BYOK · ${provider || "your key"}`
                : "FREE TIER · OpenRouter (DeepSeek → Llama → Mistral)"}
            </div>
          </div>
          {historyLoaded && (
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
          )}
        </div>

        {/* Progress bar — visible during a streaming turn */}
        {busy && (
          <ProgressBar progress={progress} chars={streamChars} />
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
                   style={{ marginBottom: 14,
                            display: "flex",
                            flexDirection: m.role === "user" ? "row-reverse" : "row" }}>
                <div style={{ maxWidth: "82%",
                              padding: "10px 14px", borderRadius: 6,
                              fontSize: 13, lineHeight: 1.55,
                              whiteSpace: "pre-wrap",
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

        {/* Next-step chips — render before the input so they sit just
            above where the dev's hands are. */}
        {nextSteps.length > 0 && (
          <div data-testid="dev-cto-chat-next-steps"
               style={{ display: "flex", gap: 6, flexWrap: "wrap",
                        padding: "10px 18px 0",
                        borderTop: "1px solid var(--dash-divider)" }}>
            <span style={{ fontSize: 9, letterSpacing: "0.18em",
                            textTransform: "uppercase",
                            color: "var(--dash-text-muted)",
                            fontFamily: "'JetBrains Mono', monospace",
                            padding: "6px 4px" }}>
              Next:
            </span>
            {nextSteps.map((s, i) => (
              <button key={i}
                       data-testid={`dev-cto-next-step-${i}`}
                       onClick={() => send(s)}
                       disabled={busy}
                       style={{ background: "rgba(255,107,0,0.06)",
                                border: "1px solid rgba(255,107,0,0.30)",
                                color: "#FFB070",
                                padding: "6px 12px",
                                borderRadius: 999,
                                fontSize: 12, cursor: busy ? "not-allowed" : "pointer",
                                display: "inline-flex", alignItems: "center", gap: 4 }}>
                {s} <ArrowRight size={11} />
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{ display: "flex", gap: 10, padding: "12px 18px",
                      borderTop: "1px solid var(--dash-divider)",
                      background: "rgba(0,0,0,0.20)" }}>
          <textarea data-testid="dev-cto-chat-input"
                     value={input} onChange={e => setInput(e.target.value)}
                     onKeyDown={onKey}
                     placeholder="Tell AUREM CTO what to build — frontend gets designed first, then the backend wires up."
                     rows={2}
                     style={{ flex: 1, background: "rgba(255,255,255,0.04)",
                              border: "1px solid var(--dash-border)",
                              color: "#F0EDE8", padding: "10px 12px",
                              borderRadius: 4, fontSize: 13,
                              fontFamily: "inherit", outline: "none",
                              resize: "vertical" }} />
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
