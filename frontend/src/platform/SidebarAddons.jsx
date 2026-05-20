/**
 * Sidebar add-ons: ORA Command Bar (top) + Sovereign Node Status (bottom).
 * Both are self-contained. Import into AuremDashboard sidebar.
 */
import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, CheckCircle2, AlertCircle, Cpu } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * ORA Command Bar — quick input that POSTs to /api/ora/command.
 * Appears at the top of the sidebar. Reply shown inline under input.
 *
 * iter 285.6 — added /command quick-chips, Ctrl+/ shortcut, expand-to-console link.
 */
const QUICK_CHIPS = [
  { label: "scan",   text: "Scan now", hint: "Full pillar scan" },
  { label: "brief",  text: "Morning brief", hint: "Today's brief" },
  { label: "blast",  text: "Launch proximity blast Toronto 15km", hint: "Fire blast campaign" },
  { label: "leads",  text: "Show hot leads", hint: "Top scoring leads" },
  { label: "health", text: "System health", hint: "Pillar status" },
];

export const OraCommandBar = () => {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [reply, setReply] = useState(null); // { ok, intent, message }
  const inputRef = useRef(null);

  const submit = async (overrideText) => {
    // iter 285.8 — when invoked from button onClick, React passes SyntheticEvent.
    // Only treat first arg as text if it's a real string.
    const raw = typeof overrideText === 'string' ? overrideText : text;
    const cmd = (raw || '').trim();
    if (!cmd || loading) return;
    setLoading(true);
    setReply(null);
    try {
      const r = await fetch(`${API}/api/ora/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: cmd, channel: 'dashboard', user: 'admin' }),
      });
      const d = await r.json();
      setReply({ ok: d.ok, intent: d.intent, message: d.reply || 'Done' });
      if (d.ok) setText('');
    } catch (e) {
      setReply({ ok: false, intent: 'ERROR', message: String(e.message || e) });
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); submit(); }
  };

  // iter 285.6 — Ctrl+/ (or Cmd+/) focus shortcut
  useEffect(() => {
    const onGlobalKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onGlobalKey);
    return () => window.removeEventListener('keydown', onGlobalKey);
  }, []);

  return (
    <div className="px-3 pb-3 relative z-10" data-testid="ora-command-bar">
      <div className="text-[8px] font-bold tracking-[2px] text-white/60 uppercase mb-1.5 flex items-center gap-1.5">
        <span className="size-1.5 rounded-full" style={{ background: '#FF6B00', boxShadow: '0 0 6px rgba(255,107,0,0.8)' }} />
        ORA COMMAND
      </div>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder="Type any command…"
          data-testid="ora-command-input"
          disabled={loading}
          className="w-full pl-2.5 pr-8 py-1.5 rounded-lg text-[11px] bg-white/[0.04] border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-[#FF6B00]/40 focus:bg-white/[0.07] transition-all"
        />
        <button
          onClick={submit}
          disabled={loading || !text.trim()}
          data-testid="ora-command-send"
          className="absolute right-1 top-1/2 -translate-y-1/2 size-6 rounded-md flex items-center justify-center hover:bg-white/10 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          aria-label="Send command"
        >
          {loading
            ? <Loader2 className="size-3 text-[#FF6B00] animate-spin" />
            : <Send className="size-3 text-[#FF6B00]" />}
        </button>
      </div>
      {reply && (
        <div
          data-testid="ora-command-reply"
          className="mt-1.5 p-2 rounded-lg text-[10px] leading-snug"
          style={{
            background: reply.ok ? 'rgba(74,222,128,0.06)' : 'rgba(239,68,68,0.06)',
            border: `1px solid ${reply.ok ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)'}`,
            color: reply.ok ? 'rgba(255,255,255,0.85)' : 'rgba(255,200,200,0.9)',
          }}>
          <div className="flex items-start gap-1.5">
            {reply.ok
              ? <CheckCircle2 className="size-3 mt-0.5 flex-shrink-0" style={{ color: '#4ade80' }} />
              : <AlertCircle className="size-3 mt-0.5 flex-shrink-0" style={{ color: '#f87171' }} />}
            <div className="flex-1 min-w-0">
              <div className="text-[8px] tracking-wider font-bold uppercase mb-0.5 flex items-center justify-between gap-2" style={{ color: reply.ok ? '#4ade80' : '#f87171' }}>
                <span>{reply.intent || 'RESULT'}</span>
                <button
                  onClick={() => setReply(null)}
                  className="text-white/50 hover:text-white/80 font-bold px-1"
                  aria-label="Clear reply"
                >×</button>
              </div>
              <div className="whitespace-pre-line max-h-[90px] overflow-y-auto break-words aurem-scroll">
                {reply.message}
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="mt-1 text-[9px] text-white/45 flex items-center justify-between gap-2">
        <span>Try: <span className="text-white/70">help</span> · <span className="text-white/70">Ctrl + /</span></span>
        <a
          href="/admin/ora-console"
          data-testid="ora-command-expand"
          className="text-[#FF6B00]/80 hover:text-[#FF6B00] transition-colors"
          title="Open full ORA Command Console"
        >
          expand →
        </a>
      </div>

      {/* iter 285.6 — quick-chips */}
      <div className="mt-1.5 flex flex-wrap gap-1" data-testid="ora-command-chips">
        {QUICK_CHIPS.map((chip) => (
          <button
            key={chip.label}
            onClick={() => submit(chip.text)}
            disabled={loading}
            data-testid={`ora-command-chip-${chip.label}`}
            title={chip.hint}
            className="px-1.5 py-0.5 rounded-md text-[9px] font-bold tracking-wide uppercase border transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: 'rgba(255,107,0,0.08)',
              borderColor: 'rgba(255,107,0,0.25)',
              color: 'rgba(255,107,0,0.9)',
            }}
          >
            /{chip.label}
          </button>
        ))}
      </div>
    </div>
  );
};


/**
 * Sovereign Node Status Pill — bottom of sidebar.
 * Polls /api/local-llm/status every 60s.
 */
export const SovereignNodeStatus = () => {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch(`${API}/api/local-llm/status`);
        if (!r.ok) throw new Error('status failed');
        const d = await r.json();
        if (!cancelled) { setStatus(d); setError(false); }
      } catch {
        if (!cancelled) { setError(true); setStatus(null); }
      }
    };
    load();
    const id = setInterval(load, 60000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const online = !!status?.online;
  const dotColor = error ? '#6b7280' : online ? '#4ade80' : '#f59e0b';
  const label = error ? 'Unknown' : online ? 'Online' : 'Offline';
  const model = status?.configured_model || 'llama3.1';

  return (
    <div
      className="mx-3 mt-3 mb-2 px-3 py-2 rounded-xl border relative z-10"
      data-testid="sovereign-node-status"
      style={{
        background: 'rgba(255,255,255,0.02)',
        borderColor: 'rgba(255,255,255,0.08)',
      }}>
      <div className="flex items-center gap-2">
        <div
          className="size-2 rounded-full flex-shrink-0"
          style={{
            background: dotColor,
            boxShadow: online ? `0 0 8px ${dotColor}` : 'none',
            animation: online ? 'pulse 2.2s ease-in-out infinite' : 'none',
          }} />
        <Cpu className="size-3 text-white/65 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-[9px] tracking-[2px] font-bold uppercase text-white/70 leading-tight">
            Sovereign Node
          </div>
          <div className="text-[9px] text-white/55 truncate" title={model}>
            {label} · {model}
          </div>
        </div>
      </div>
      {status?.model_count > 0 && (
        <div className="mt-1 text-[8px] text-white/45">
          {status.model_count} models · {status.tunnel || 'direct'} · {status.cost || '$0/req'}
        </div>
      )}
    </div>
  );
};
