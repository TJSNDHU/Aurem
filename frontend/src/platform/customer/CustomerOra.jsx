/**
 * CustomerOra — Fully functional ORA chat for customers.
 * iter 278: replaced iframe stub with a real chat UI that calls
 * /api/aurem/chat (verified working, RAG-powered, returns assistant response).
 *
 * Features:
 *   - Message history with user + assistant bubbles
 *   - Streaming-style typing indicator during LLM call
 *   - Persist session_id so ORA remembers context across turns
 *   - Scroll-to-bottom on new message
 *   - Error surfacing (no silent failures)
 */
import React, { useState, useEffect, useRef } from "react";
import { Send, Loader2, Sparkles, RefreshCw } from "lucide-react";
import { getPlatformToken } from "../../utils/secureTokenStore";

const API = process.env.REACT_APP_BACKEND_URL || "";

const COLORS = {
  bg:     "#08080F",
  panel:  "rgba(255,255,255,0.04)",
  border: "rgba(212,175,55,0.18)",
  accent: "#D4AF37",
  accent2:"#FF6B00",
  text:   "#F0EADC",
  textD:  "#A8A08F",
};

function MessageBubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div
      data-testid={`ora-msg-${role}`}
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: 12,
      }}
    >
      <div
        style={{
          maxWidth: "78%",
          padding: "10px 14px",
          borderRadius: 14,
          background: isUser
            ? "rgba(212,175,55,0.15)"
            : "rgba(255,255,255,0.05)",
          border: `1px solid ${
            isUser ? "rgba(212,175,55,0.35)" : "rgba(255,255,255,0.08)"
          }`,
          color: COLORS.text,
          fontSize: 14,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          boxShadow: "0 4px 14px rgba(0,0,0,0.25)",
        }}
      >
        {content}
      </div>
    </div>
  );
}

export default function CustomerOra() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi! I'm ORA — your AI sales co-pilot. Ask me about your leads, pipeline, campaigns, or anything you want me to do.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  const send = async () => {
    const msg = input.trim();
    if (!msg || busy) return;
    setInput("");
    setErr("");
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setBusy(true);
    try {
      const token = getPlatformToken();
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      const body = { message: msg };
      if (sessionId) body.session_id = sessionId;
      // iter 279 — tenant isolation: attach business_id/tenant_id if available
      try {
        const raw = localStorage.getItem("platform_user")
                 || sessionStorage.getItem("platform_user")
                 || localStorage.getItem("aurem_user");
        if (raw) {
          const u = JSON.parse(raw);
          const tid = u.business_id || u.tenant_id || u._id || u.id || u.email;
          if (tid) body.tenant_id = String(tid);
        }
      } catch { /* ignore */ }

      const r = await fetch(`${API}/api/aurem/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (d.session_id && !sessionId) setSessionId(d.session_id);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: d.response || "(no response)" },
      ]);
    } catch (e) {
      setErr(String(e.message || e));
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Something went wrong reaching ORA. Please try again.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const onKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const reset = () => {
    setMessages([
      {
        role: "assistant",
        content:
          "Fresh session. Ask me anything — leads, campaigns, strategy, or give me a task.",
      },
    ]);
    setSessionId(null);
    setErr("");
  };

  return (
    <div
      data-testid="customer-ora"
      style={{
        height: "calc(100vh - 110px)",
        borderRadius: 22,
        overflow: "hidden",
        background: COLORS.panel,
        backdropFilter: "blur(26px) saturate(150%)",
        WebkitBackdropFilter: "blur(26px) saturate(150%)",
        border: `1px solid ${COLORS.border}`,
        boxShadow:
          "0 28px 70px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.08)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 20px",
          borderBottom: `1px solid ${COLORS.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              background:
                "linear-gradient(135deg, rgba(212,175,55,0.2), rgba(255,107,0,0.15))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: `1px solid ${COLORS.border}`,
            }}
          >
            <Sparkles size={16} style={{ color: COLORS.accent }} />
          </div>
          <div>
            <div
              style={{
                color: COLORS.text,
                fontSize: 14,
                fontWeight: 600,
                fontFamily: "'Jost',sans-serif",
                letterSpacing: "0.5px",
              }}
            >
              ORA · Your AI Sales Co-Pilot
            </div>
            <div
              style={{
                color: COLORS.textD,
                fontSize: 10,
                marginTop: 1,
                textTransform: "uppercase",
                letterSpacing: 1.5,
              }}
            >
              {busy ? "Thinking…" : "Ready"}
              {sessionId ? ` · session ${sessionId.slice(0, 8)}` : ""}
            </div>
          </div>
        </div>
        <button
          onClick={reset}
          disabled={busy}
          data-testid="ora-reset-btn"
          title="Start a fresh session"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "5px 12px",
            background: "rgba(255,255,255,0.03)",
            border: `1px solid ${COLORS.border}`,
            borderRadius: 8,
            color: COLORS.textD,
            fontSize: 11,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.4 : 1,
          }}
        >
          <RefreshCw size={12} />
          New
        </button>
      </div>

      {/* Message log */}
      <div
        ref={scrollRef}
        data-testid="ora-messages"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "18px 20px",
          scrollBehavior: "smooth",
        }}
      >
        {messages.map((m, i) => (
          <MessageBubble key={i} role={m.role} content={m.content} />
        ))}
        {busy ? (
          <div
            data-testid="ora-typing"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 14px",
              color: COLORS.textD,
              fontSize: 12,
              fontStyle: "italic",
            }}
          >
            <Loader2
              size={14}
              style={{ animation: "spin 1s linear infinite" }}
            />
            ORA is thinking…
          </div>
        ) : null}
        {err ? (
          <div
            style={{
              color: "#EF4444",
              fontSize: 11,
              padding: "4px 14px",
              fontFamily: "monospace",
            }}
          >
            error: {err}
          </div>
        ) : null}
      </div>

      {/* Composer */}
      <div
        style={{
          padding: "14px 20px",
          borderTop: `1px solid ${COLORS.border}`,
          background: "rgba(0,0,0,0.25)",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-end",
          }}
        >
          <textarea
            data-testid="ora-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask ORA anything — e.g., 'What's my hottest lead today?'"
            disabled={busy}
            rows={1}
            style={{
              flex: 1,
              padding: "10px 14px",
              background: "rgba(255,255,255,0.04)",
              border: `1px solid ${COLORS.border}`,
              borderRadius: 10,
              color: COLORS.text,
              fontSize: 14,
              fontFamily: "inherit",
              resize: "none",
              outline: "none",
              minHeight: 42,
              maxHeight: 120,
            }}
          />
          <button
            onClick={send}
            disabled={busy || !input.trim()}
            data-testid="ora-send-btn"
            style={{
              padding: "10px 16px",
              background: busy || !input.trim()
                ? "rgba(212,175,55,0.08)"
                : `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.accent2})`,
              border: "none",
              borderRadius: 10,
              color: busy || !input.trim() ? COLORS.textD : "#08080F",
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: "0.5px",
              cursor: busy || !input.trim() ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              minHeight: 42,
            }}
          >
            {busy ? (
              <Loader2
                size={14}
                style={{ animation: "spin 1s linear infinite" }}
              />
            ) : (
              <Send size={14} />
            )}
            Send
          </button>
        </div>
        <div
          style={{
            fontSize: 10,
            color: COLORS.textD,
            marginTop: 6,
            textAlign: "center",
            letterSpacing: 0.5,
          }}
        >
          ORA uses live context from your pipeline, leads, and campaigns.
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
      `}</style>
    </div>
  );
}
