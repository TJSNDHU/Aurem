/**
 * CommandPalette.jsx — Founder velocity multiplier (⌘K / Ctrl+K).
 *
 * What it does
 *   • Global keyboard trap (Cmd+K / Ctrl+K) opens a floating search box.
 *   • Type to filter local commands (navigate tabs, logout, etc).
 *   • Press Enter on a free-text query → ships it to ORA
 *     (`/api/ora/agent/run-async`) and shows the reply inline.
 *   • Arrow keys + Enter for keyboard-first navigation.
 *
 * Drop-in: render <CommandPalette tabs={TABS} setActive={setActive} />
 * inside OraAdminUnified; it self-mounts the keydown listener.
 */
import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search, Terminal, ArrowRight, Loader2, Sparkles, LogOut, Crown,
} from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL || "";
const GOLD = "#D4AF37";
const TEXT = "#F0EADC";
const TEXT_DIM = "#A8A08F";
const BORDER = "rgba(212,175,55,0.22)";
const PANEL_BG = "rgba(14,14,22,0.96)";

function readToken() {
  try {
    return (
      sessionStorage.getItem("platform_token") ||
      localStorage.getItem("platform_token") ||
      localStorage.getItem("aurem_admin_token") ||
      sessionStorage.getItem("aurem_admin_token") ||
      localStorage.getItem("token") ||
      ""
    );
  } catch { return ""; }
}

function newSessionId() {
  return "palette-" + Math.random().toString(36).slice(2, 10);
}

export default function CommandPalette({ tabs = [], setActive }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [oraBusy, setOraBusy] = useState(false);
  const [oraReply, setOraReply] = useState("");
  const [oraError, setOraError] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // Global hotkey: Cmd+K (mac) / Ctrl+K (win/linux).
  useEffect(() => {
    function onKey(e) {
      const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k";
      if (isCmdK) {
        e.preventDefault();
        setOpen((v) => !v);
        setOraReply("");
        setOraError("");
      } else if (e.key === "Escape" && open) {
        e.preventDefault();
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 30);
      return () => clearTimeout(t);
    }
    setQuery("");
    setHighlight(0);
  }, [open]);

  const localCommands = useMemo(() => {
    const tabCmds = tabs.map((t) => ({
      id: `tab-${t.id}`,
      icon: t.icon,
      label: `Go to ${t.label}`,
      hint: t.id,
      run: () => { setActive?.(t.id); setOpen(false); },
    }));
    const sys = [
      {
        id: "sys-logout",
        icon: LogOut,
        label: "Logout",
        hint: "clear session",
        run: () => {
          try { localStorage.clear(); sessionStorage.clear(); } catch {}
          navigate("/admin/login");
        },
      },
      {
        id: "sys-home",
        icon: Crown,
        label: "Back to AUREM home",
        hint: "/",
        run: () => navigate("/"),
      },
    ];
    return [...tabCmds, ...sys];
  }, [tabs, setActive, navigate]);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? localCommands.filter((c) =>
        c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q))
    : localCommands;

  // When no local command matches but the user typed something, offer to
  // ship the raw query to ORA.
  const oraFallback = q && filtered.length === 0;

  const onKeyDown = useCallback(async (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, Math.max(filtered.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered.length > 0) {
        filtered[highlight]?.run?.();
        return;
      }
      if (q) {
        await askOra(query.trim());
      }
    }
  }, [filtered, highlight, q, query]);

  async function askOra(text) {
    setOraBusy(true);
    setOraError("");
    setOraReply("");
    const token = readToken();
    if (!token) {
      setOraError("No admin token. Login first.");
      setOraBusy(false);
      return;
    }
    try {
      const sid = newSessionId();
      const startRes = await fetch(`${API}/api/ora/agent/run-async`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ session_id: sid, text }),
      });
      if (!startRes.ok) {
        const detail = await safeJson(startRes);
        throw new Error(detail?.detail || `HTTP ${startRes.status}`);
      }
      const job = await startRes.json();
      const jobId = job.job_id || job.id;
      if (!jobId) throw new Error("ORA returned no job_id");

      // Poll status — 60 attempts × 1.2s = ~72s ceiling for a long ORA turn.
      let final = null;
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 1200));
        const pr = await fetch(
          `${API}/api/ora/agent/status/${encodeURIComponent(jobId)}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!pr.ok) continue;
        const d = await pr.json();
        if (d.status === "done" || d.status === "complete" || d.status === "completed") {
          final = d;
          break;
        }
        if (d.status === "error" || d.status === "failed") {
          throw new Error(d.error || "ORA failed");
        }
      }
      if (!final) {
        setOraError("ORA is still thinking… open Chat tab to continue.");
      } else {
        const result = final.result || final.reply || final;
        const reply =
          (typeof result === "string" && result) ||
          result?.reply ||
          result?.message ||
          result?.text ||
          JSON.stringify(result).slice(0, 800);
        setOraReply(reply);
      }
    } catch (err) {
      setOraError(err?.message || "ORA request failed");
    } finally {
      setOraBusy(false);
    }
  }

  if (!open) return null;

  return (
    <div
      data-testid="command-palette"
      onClick={() => setOpen(false)}
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(2,2,6,0.62)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        padding: "10vh 16px",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(640px, 100%)",
          background: PANEL_BG,
          border: `1px solid ${BORDER}`,
          borderRadius: 14,
          boxShadow: "0 24px 80px rgba(0,0,0,0.55)",
          overflow: "hidden",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif",
        }}
      >
        {/* Search row */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "14px 16px", borderBottom: `1px solid ${BORDER}`,
        }}>
          <Search size={16} color={GOLD} />
          <input
            ref={inputRef}
            data-testid="command-palette-input"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setHighlight(0); }}
            onKeyDown={onKeyDown}
            placeholder="Type a command or ask ORA anything…"
            spellCheck={false}
            autoComplete="off"
            style={{
              flex: 1, background: "transparent", border: "none",
              outline: "none", color: TEXT, fontSize: 15,
            }}
          />
          <kbd style={kbd}>esc</kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: "50vh", overflowY: "auto" }}>
          {filtered.length > 0 && (
            <div style={{ padding: "8px 6px" }}>
              <div style={sectionLabel}>Quick actions</div>
              {filtered.map((c, idx) => {
                const Icon = c.icon || Terminal;
                const active = idx === highlight;
                return (
                  <button
                    key={c.id}
                    data-testid={`command-palette-item-${c.id}`}
                    onMouseEnter={() => setHighlight(idx)}
                    onClick={c.run}
                    style={{
                      ...rowBtn,
                      background: active ? "rgba(212,175,55,0.10)" : "transparent",
                      color: active ? GOLD : TEXT,
                    }}
                  >
                    <Icon size={15} />
                    <span style={{ flex: 1, textAlign: "left" }}>{c.label}</span>
                    {c.hint && (
                      <span style={{ fontSize: 11, color: TEXT_DIM }}>{c.hint}</span>
                    )}
                    {active && <ArrowRight size={13} color={GOLD} />}
                  </button>
                );
              })}
            </div>
          )}

          {oraFallback && (
            <div style={{ padding: "8px 6px", borderTop: `1px solid ${BORDER}` }}>
              <div style={sectionLabel}>Ask ORA</div>
              <button
                data-testid="command-palette-ask-ora"
                onClick={() => askOra(query.trim())}
                disabled={oraBusy}
                style={{
                  ...rowBtn,
                  background: "rgba(212,175,55,0.08)",
                  color: GOLD,
                  cursor: oraBusy ? "wait" : "pointer",
                }}
              >
                {oraBusy ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                <span style={{ flex: 1, textAlign: "left" }}>
                  {oraBusy ? "ORA is thinking…" : `Send to ORA: "${query.trim()}"`}
                </span>
                <kbd style={kbd}>enter</kbd>
              </button>
            </div>
          )}

          {(oraReply || oraError) && (
            <div data-testid="command-palette-ora-output"
                 style={{ padding: "12px 16px 16px",
                          borderTop: `1px solid ${BORDER}` }}>
              {oraError && (
                <div style={{ color: "#FF8A8A", fontSize: 13 }}>
                  ⚠ {oraError}
                </div>
              )}
              {oraReply && (
                <div style={{
                  whiteSpace: "pre-wrap", color: TEXT, fontSize: 13.5,
                  lineHeight: 1.55,
                }}>
                  <div style={{ color: GOLD, fontSize: 11, letterSpacing: 1,
                                marginBottom: 6, textTransform: "uppercase" }}>
                    ORA
                  </div>
                  {oraReply}
                </div>
              )}
            </div>
          )}

          {!filtered.length && !oraFallback && (
            <div style={{ padding: 24, color: TEXT_DIM, fontSize: 13,
                          textAlign: "center" }}>
              Type to search commands or ask ORA.
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "8px 14px", borderTop: `1px solid ${BORDER}`,
          background: "rgba(0,0,0,0.25)", color: TEXT_DIM, fontSize: 11,
        }}>
          <span><kbd style={kbd}>↑</kbd> <kbd style={kbd}>↓</kbd> move</span>
          <span><kbd style={kbd}>enter</kbd> select</span>
          <span style={{ marginLeft: "auto" }}>⌘K · ORA Command Palette</span>
        </div>
      </div>

      <style>{`
        .spin { animation: cpspin 1s linear infinite; }
        @keyframes cpspin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

async function safeJson(res) {
  try { return await res.json(); } catch { return null; }
}

const sectionLabel = {
  fontSize: 10, letterSpacing: 1.5, textTransform: "uppercase",
  color: TEXT_DIM, padding: "6px 10px 4px",
};

const rowBtn = {
  width: "100%", display: "flex", alignItems: "center", gap: 10,
  padding: "10px 12px", borderRadius: 8, border: "none",
  cursor: "pointer", fontSize: 14, textAlign: "left",
  transition: "background 120ms ease, color 120ms ease",
};

const kbd = {
  display: "inline-flex", alignItems: "center", justifyContent: "center",
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
  fontSize: 10, color: TEXT_DIM,
  background: "rgba(255,255,255,0.06)",
  border: `1px solid ${BORDER}`, borderRadius: 4,
  padding: "2px 6px", lineHeight: 1.2,
};
