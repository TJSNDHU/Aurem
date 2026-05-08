/**
 * ORAWidget — Persistent draggable support helper
 * ==================================================
 * - Stays mounted at App root → survives route changes
 * - Draggable (mouse + touch) anywhere on viewport
 * - Resizable from bottom-right corner
 * - Minimize → 48px header bar; maximize back to last size
 * - File / image upload support (paperclip icon)
 * - Persists position + size + minimized state in localStorage
 * - Dark obsidian + gold (#D4AF37) AUREM aesthetic
 * - Backend: POST /api/ora/support-chat (graceful fallback if 404)
 */
import React, { useState, useRef, useEffect, useCallback } from "react";

const STORAGE_KEY = "aurem.ora_widget.v1";
const ACCENT = "#D4AF37";
const BG_DARK = "#0A0A0A";
const BORDER = "rgba(212, 175, 55, 0.25)";

const DEFAULT_STATE = {
  position: { x: null, y: null },   // null → bottom-right anchor
  size: { w: 340, h: 460 },
  minimized: false,
  visited: false,
};

const loadState = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_STATE };
    return { ...DEFAULT_STATE, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_STATE };
  }
};

const saveState = (s) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch {}
};

export default function ORAWidget() {
  const [state, setState] = useState(loadState);
  const [messages, setMessages] = useState([
    { role: "ora", text: "Hi! I'm ORA. Stuck somewhere? Type or drop a screenshot — I'll help." }
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const widgetRef = useRef(null);
  const dragRef = useRef({ active: false, dx: 0, dy: 0 });
  const resizeRef = useRef({ active: false, sx: 0, sy: 0, w: 0, h: 0 });
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // First-visit auto-open is the default state (minimized: false). Returning
  // visitors get whatever they last set (minimized true if they collapsed it).
  useEffect(() => {
    if (!state.visited) {
      const next = { ...state, visited: true, minimized: false };
      setState(next);
      saveState(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { saveState(state); }, [state]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // ─── Drag handlers ─────────────────────────────────────────
  const onHeaderPointerDown = (e) => {
    if (e.target.closest("[data-no-drag]")) return;
    const node = widgetRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    dragRef.current = {
      active: true,
      dx: e.clientX - rect.left,
      dy: e.clientY - rect.top,
    };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onHeaderPointerMove = (e) => {
    if (!dragRef.current.active) return;
    const node = widgetRef.current;
    const w = node?.offsetWidth || state.size.w;
    const h = node?.offsetHeight || (state.minimized ? 48 : state.size.h);
    const maxX = window.innerWidth - w - 4;
    const maxY = window.innerHeight - h - 4;
    const x = Math.max(4, Math.min(maxX, e.clientX - dragRef.current.dx));
    const y = Math.max(4, Math.min(maxY, e.clientY - dragRef.current.dy));
    setState((s) => ({ ...s, position: { x, y } }));
  };
  const onHeaderPointerUp = (e) => {
    dragRef.current.active = false;
    try { e.currentTarget.releasePointerCapture?.(e.pointerId); } catch {}
  };

  // ─── Resize handlers ───────────────────────────────────────
  const onResizePointerDown = (e) => {
    e.stopPropagation();
    resizeRef.current = {
      active: true,
      sx: e.clientX,
      sy: e.clientY,
      w: state.size.w,
      h: state.size.h,
    };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onResizePointerMove = (e) => {
    if (!resizeRef.current.active) return;
    const dx = e.clientX - resizeRef.current.sx;
    const dy = e.clientY - resizeRef.current.sy;
    const w = Math.max(280, Math.min(720, resizeRef.current.w + dx));
    const h = Math.max(320, Math.min(800, resizeRef.current.h + dy));
    setState((s) => ({ ...s, size: { w, h } }));
  };
  const onResizePointerUp = (e) => {
    resizeRef.current.active = false;
    try { e.currentTarget.releasePointerCapture?.(e.pointerId); } catch {}
  };

  // ─── Send message ──────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text && attachments.length === 0) return;
    setSending(true);
    const userMsg = {
      role: "user",
      text: text || "(screenshot attached)",
      attachments: attachments.map(a => ({ name: a.name, size: a.size })),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    const filesToSend = attachments;
    setAttachments([]);

    try {
      const apiBase = process.env.REACT_APP_BACKEND_URL || window.location.origin;
      const fd = new FormData();
      fd.append("message", text);
      fd.append("session_id", localStorage.getItem("aurem.ora_session") || `ora-${Date.now()}`);
      fd.append("page_url", window.location.href);
      filesToSend.forEach((f) => fd.append("attachments", f, f.name));
      const res = await fetch(`${apiBase}/api/ora/support-chat`, {
        method: "POST",
        body: fd,
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((m) => [...m, {
          role: "ora",
          text: data.response || data.reply || "Got it — I've logged this. A human will follow up if needed.",
        }]);
      } else {
        // Graceful fallback: still acknowledge without breaking UX.
        setMessages((m) => [...m, {
          role: "ora",
          text: "Got it — I've noted this. (Live chat backend not yet wired; we'll follow up by email if you signed in.)",
        }]);
      }
    } catch (err) {
      setMessages((m) => [...m, {
        role: "ora",
        text: "I couldn't reach the support brain just now — please email teji@aurem.live and we'll respond fast.",
      }]);
    } finally {
      setSending(false);
    }
  }, [input, attachments]);

  // ─── Attachments ───────────────────────────────────────────
  const handleFiles = (files) => {
    const arr = Array.from(files || []).slice(0, 4);
    // Cap each at 5 MB to avoid huge uploads
    const filtered = arr.filter((f) => f.size <= 5 * 1024 * 1024);
    setAttachments((cur) => [...cur, ...filtered].slice(0, 4));
  };
  const onPaste = (e) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files = [];
    for (const it of items) {
      if (it.kind === "file") {
        const f = it.getAsFile();
        if (f) files.push(f);
      }
    }
    if (files.length) {
      e.preventDefault();
      handleFiles(files);
    }
  };

  // ─── Position / sizing ─────────────────────────────────────
  const widgetStyle = state.position.x === null
    ? { right: 16, bottom: 16 }
    : { left: state.position.x, top: state.position.y };

  const heightStyle = state.minimized ? { height: 48 } : { height: state.size.h };

  return (
    <div
      ref={widgetRef}
      data-testid="ora-widget"
      style={{
        position: "fixed",
        zIndex: 2147483600,
        width: state.size.w,
        ...heightStyle,
        ...widgetStyle,
        background: BG_DARK,
        border: `1px solid ${BORDER}`,
        borderRadius: 14,
        boxShadow: "0 24px 48px rgba(0,0,0,0.55), 0 0 0 1px rgba(212,175,55,0.06)",
        color: "#F4F4F4",
        fontFamily: "Inter, system-ui, sans-serif",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        backdropFilter: "blur(8px)",
        userSelect: dragRef.current.active || resizeRef.current.active ? "none" : "auto",
        transition: dragRef.current.active ? "none" : "height 0.2s ease",
      }}
    >
      {/* Header (drag handle) */}
      <div
        data-testid="ora-widget-header"
        onPointerDown={onHeaderPointerDown}
        onPointerMove={onHeaderPointerMove}
        onPointerUp={onHeaderPointerUp}
        style={{
          height: 48,
          padding: "0 12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "grab",
          background: "linear-gradient(180deg, rgba(212,175,55,0.10), rgba(212,175,55,0.02))",
          borderBottom: state.minimized ? "none" : `1px solid ${BORDER}`,
          flex: "0 0 48px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, pointerEvents: "none" }}>
          <span style={{
            width: 8, height: 8, borderRadius: "50%", background: ACCENT,
            boxShadow: `0 0 10px ${ACCENT}`,
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: 0.3 }}>
            ORA <span style={{ color: "#888", fontWeight: 400 }}>— Need Help?</span>
          </span>
        </div>
        <div data-no-drag style={{ display: "flex", gap: 4 }}>
          <button
            data-testid="ora-widget-toggle-btn"
            onClick={() => setState((s) => ({ ...s, minimized: !s.minimized }))}
            aria-label={state.minimized ? "Expand" : "Minimize"}
            style={iconBtnStyle}
            title={state.minimized ? "Expand" : "Minimize"}
          >
            {state.minimized ? "▴" : "▾"}
          </button>
        </div>
      </div>

      {/* Body — only when expanded */}
      {!state.minimized && (
        <>
          <div
            data-testid="ora-widget-messages"
            style={{
              flex: 1,
              overflowY: "auto",
              padding: 12,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              fontSize: 13,
              lineHeight: 1.5,
            }}
          >
            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  background: m.role === "user"
                    ? "rgba(212,175,55,0.14)"
                    : "rgba(255,255,255,0.04)",
                  border: `1px solid ${m.role === "user" ? "rgba(212,175,55,0.28)" : "rgba(255,255,255,0.06)"}`,
                  color: m.role === "user" ? "#F4E9C7" : "#E8E8E8",
                  padding: "8px 10px",
                  borderRadius: 10,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {m.text}
                {m.attachments && m.attachments.length > 0 && (
                  <div style={{ marginTop: 6, fontSize: 11, color: "#999" }}>
                    📎 {m.attachments.map(a => a.name).join(", ")}
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div style={{ alignSelf: "flex-start", color: "#888", fontSize: 12 }}>ORA is thinking…</div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Attachments preview */}
          {attachments.length > 0 && (
            <div style={{
              padding: "6px 12px",
              borderTop: `1px solid ${BORDER}`,
              display: "flex",
              gap: 6,
              flexWrap: "wrap",
              fontSize: 11,
              color: "#bbb",
              background: "rgba(255,255,255,0.02)",
            }}>
              {attachments.map((a, i) => (
                <span
                  key={i}
                  style={{
                    padding: "3px 8px",
                    background: "rgba(212,175,55,0.10)",
                    border: `1px solid ${BORDER}`,
                    borderRadius: 6,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  📎 {a.name}
                  <button
                    data-testid={`ora-widget-remove-attachment-${i}`}
                    onClick={() => setAttachments(cur => cur.filter((_, idx) => idx !== i))}
                    style={{ ...iconBtnStyle, padding: 0, width: 16, height: 16, fontSize: 11 }}
                    aria-label="Remove attachment"
                  >×</button>
                </span>
              ))}
            </div>
          )}

          {/* Composer */}
          <div
            data-testid="ora-widget-composer"
            style={{
              padding: 8,
              borderTop: `1px solid ${BORDER}`,
              display: "flex",
              alignItems: "flex-end",
              gap: 6,
              background: "rgba(0,0,0,0.4)",
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,application/pdf,.txt,.log"
              multiple
              style={{ display: "none" }}
              onChange={(e) => handleFiles(e.target.files)}
              data-testid="ora-widget-file-input"
            />
            <button
              data-testid="ora-widget-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              style={iconBtnStyle}
              aria-label="Attach screenshot"
              title="Attach screenshot or file"
            >📎</button>
            <textarea
              data-testid="ora-widget-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onPaste={onPaste}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Where are you stuck?"
              rows={1}
              style={{
                flex: 1,
                resize: "none",
                background: "rgba(255,255,255,0.04)",
                border: `1px solid ${BORDER}`,
                borderRadius: 8,
                color: "#F4F4F4",
                padding: "8px 10px",
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
                maxHeight: 120,
                lineHeight: 1.4,
              }}
            />
            <button
              data-testid="ora-widget-send-btn"
              onClick={handleSend}
              disabled={sending || (!input.trim() && attachments.length === 0)}
              style={{
                ...iconBtnStyle,
                background: ACCENT,
                color: "#0A0A0A",
                fontWeight: 700,
                width: "auto",
                padding: "0 14px",
                opacity: (sending || (!input.trim() && attachments.length === 0)) ? 0.5 : 1,
              }}
              aria-label="Send"
            >Send</button>
          </div>

          {/* Resize handle (bottom-right) — role=button so aria-label is permitted */}
          <div
            data-testid="ora-widget-resize-handle"
            role="button"
            tabIndex={0}
            onPointerDown={onResizePointerDown}
            onPointerMove={onResizePointerMove}
            onPointerUp={onResizePointerUp}
            style={{
              position: "absolute",
              right: 0,
              bottom: 0,
              width: 16,
              height: 16,
              cursor: "nwse-resize",
              background: "linear-gradient(135deg, transparent 50%, rgba(212,175,55,0.55) 50%)",
              borderBottomRightRadius: 14,
              touchAction: "none",
            }}
            aria-label="Resize ORA widget"
          />
        </>
      )}
    </div>
  );
}

const iconBtnStyle = {
  width: 28,
  height: 28,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 6,
  color: "#E8E8E8",
  cursor: "pointer",
  fontSize: 14,
  lineHeight: 1,
  padding: 0,
  outline: "none",
};
