/**
 * DevCtoChatPanel — iter 332b D-10
 *
 * The chat window the founder said was missing from the dev portal.
 * Lives on /developers/dashboard. Calls POST /api/developers/cto/chat
 * which transparently routes to:
 *   - the dev's BYOK provider if configured
 *   - otherwise DeepSeek V3 (free tier) with Groq Llama 3.3 fallback
 *
 * Token-low popup fires when tokens_remaining < 100 after a reply.
 */
import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Sparkles, AlertTriangle } from "lucide-react";
import { devAuthHeaders } from "./DeveloperShell";

const API = process.env.REACT_APP_BACKEND_URL || "";
const LOW_THRESHOLD = 100;

export default function DevCtoChatPanel({ onTokensUpdate }) {
  const navigate = useNavigate();
  const scrollRef = useRef(null);

  const [messages, setMessages] = useState([
    { role: "assistant", content:
      "Hi — I'm AUREM CTO. Free tier is active, no setup needed. " +
      "Ask me anything: code reviews, refactors, debugging, architecture. " +
      "Plain English answers. What are you building?" },
  ]);
  const [input, setInput]     = useState("");
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState(null);
  const [tier, setTier]       = useState("free");
  const [provider, setProvider] = useState("");
  const [showLowModal, setShowLowModal] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setError(null);
    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    try {
      // iter 332b D-14 — trim the rolling history so we never push a
      // mega-payload that takes 90+ seconds to generate.
      const history = next.slice(-6).map(m => ({
        role: m.role,
        content: String(m.content || "").slice(0, 2000),
      }));
      // iter 332b D-15 — streaming. POST to /chat/stream, read SSE
      // chunks as they arrive, append text deltas to the trailing
      // assistant bubble. Feels 10× faster.
      const r = await fetch(`${API}/api/developers/cto/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...devAuthHeaders() },
        body: JSON.stringify({ messages: history }),
      });
      if (!r.ok) {
        // Server-side rejection (auth, validation). Read once + show friendly text.
        const raw = await r.text();
        const friendly = r.status === 524
          ? "The free-tier model took too long. Please rephrase or try again."
          : (() => { try { return JSON.parse(raw).detail || JSON.parse(raw).message; }
                    catch { return `HTTP ${r.status}`; } })();
        throw new Error(friendly);
      }
      // Append an empty assistant bubble we'll fill as tokens arrive
      setMessages(m => [...m, { role: "assistant", content: "" }]);
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let receivedAny = false;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE events split by blank-line
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
                // Replace the (probably-empty) trailing assistant bubble
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
      // Roll back the empty bubble we appended if it's still blank
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

  return (
    <>
      <div data-testid="dev-cto-chat-panel" className="av2-card"
           style={{ marginBottom: 16, padding: 0, overflow: "hidden",
                    border: "1px solid rgba(255,107,0,0.18)" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 10,
                      padding: "14px 18px",
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
        </div>

        {/* Message list */}
        <div ref={scrollRef}
             data-testid="dev-cto-chat-messages"
             style={{ maxHeight: 360, minHeight: 240, overflowY: "auto",
                      padding: "14px 18px",
                      background: "rgba(0,0,0,0.30)" }}>
          {messages.map((m, i) => (
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
                {m.content}
              </div>
            </div>
          ))}
          {busy && (
            <div data-testid="dev-cto-chat-busy"
                 style={{ fontSize: 12, color: "var(--dash-text-muted)",
                          fontStyle: "italic" }}>
              Thinking…
            </div>
          )}
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

        {/* Input */}
        <div style={{ display: "flex", gap: 10, padding: "12px 18px",
                      borderTop: "1px solid var(--dash-divider)",
                      background: "rgba(0,0,0,0.20)" }}>
          <textarea data-testid="dev-cto-chat-input"
                     value={input} onChange={e => setInput(e.target.value)}
                     onKeyDown={onKey}
                     placeholder="Ask AUREM CTO anything — code, debug, refactor…"
                     rows={2}
                     style={{ flex: 1, background: "rgba(255,255,255,0.04)",
                              border: "1px solid var(--dash-border)",
                              color: "#F0EDE8", padding: "10px 12px",
                              borderRadius: 4, fontSize: 13,
                              fontFamily: "inherit", outline: "none",
                              resize: "vertical" }} />
          <button data-testid="dev-cto-chat-send"
                   onClick={send} disabled={busy || !input.trim()}
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

      {/* Token-low modal */}
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
              tokens</strong> ($0.27 per million vs the platform's free
              tier limits) and never hit a wall again. Takes 60 seconds.
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
