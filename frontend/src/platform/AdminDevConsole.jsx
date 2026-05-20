/**
 * AdminDevConsole — Floating F12-style overlay for AUREM admins
 * ═════════════════════════════════════════════════════════════════
 *
 * Mounted globally on the admin dashboard. Collapsed by default (tiny FAB
 * bottom-right). Click → slides open a 4-tab panel aggregating every
 * observability signal we already run:
 *
 *   • Sentinel   — live client-error feed from /api/admin/sentinel/*
 *   • QA Pulse   — critical endpoint health from /api/qa/pulse/latest
 *   • Suggests   — AI-generated fix suggestions (admin reviews/approves)
 *   • Console    — in-browser console.log/error/warn mirror (no F12 needed)
 *
 * Auto-refreshes every 15s when open. Hidden for non-admins.
 * Keyboard shortcut: Ctrl+Shift+D toggles open/close.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Shield, Activity, Sparkles, Terminal, X, RefreshCw, ExternalLink,
  AlertTriangle, CheckCircle2, Clock, TrendingDown, TrendingUp, Bug,
  ChevronDown, ChevronUp,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';
const GOLD = '#D4AF37';
const PANEL_WIDTH = 460;

// ───── console mirror (captured at module load so we don't miss early errors)
const _consoleRingBuffer = [];
const MAX_BUFFER = 200;

function _pushLog(level, args) {
  try {
    const msg = args.map(a => {
      if (typeof a === 'string') return a;
      if (a instanceof Error) return `${a.name}: ${a.message}`;
      try { return JSON.stringify(a); } catch { return String(a); }
    }).join(' ');
    _consoleRingBuffer.push({
      level,
      msg: msg.slice(0, 500),
      ts: new Date().toISOString(),
    });
    if (_consoleRingBuffer.length > MAX_BUFFER) _consoleRingBuffer.shift();
  } catch { /* swallow */ }
}

if (typeof window !== 'undefined' && !window.__AUREM_CONSOLE_HOOKED__) {
  window.__AUREM_CONSOLE_HOOKED__ = true;
  ['log', 'warn', 'error', 'info'].forEach(level => {
    const orig = console[level].bind(console);
    console[level] = (...args) => { _pushLog(level, args); orig(...args); };
  });
  window.addEventListener('error', (e) => {
    _pushLog('error', [`[window.error] ${e.message} @ ${e.filename}:${e.lineno}`]);
  });
  window.addEventListener('unhandledrejection', (e) => {
    _pushLog('error', [`[unhandledrejection] ${e.reason?.message || e.reason || 'unknown'}`]);
  });
}

// ══════════════════════════════════════════════════════════════════════
//                              Component
// ══════════════════════════════════════════════════════════════════════
export default function AdminDevConsole({ token, isAdmin }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('sentinel');
  const [overview, setOverview] = useState(null);
  const [errors, setErrors] = useState([]);
  const [pulse, setPulse] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [consoleBump, setConsoleBump] = useState(0);
  const pollRef = useRef(null);

  // ─── keyboard shortcut: Ctrl+Shift+D
  useEffect(() => {
    if (!isAdmin) return undefined;
    const onKey = (e) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isAdmin]);

  // ─── console mirror tick (only when on Console tab + open)
  useEffect(() => {
    if (!open || tab !== 'console') return undefined;
    const t = setInterval(() => setConsoleBump((v) => v + 1), 2000);
    return () => clearInterval(t);
  }, [open, tab]);

  const fetchAll = useCallback(async () => {
    if (!token) return;
    setBusy(true);
    const H = { Authorization: `Bearer ${token}` };
    try {
      const [ovr, errs, plz, sug] = await Promise.allSettled([
        fetch(`${API}/api/admin/sentinel/overview`, { headers: H }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/sentinel/errors?limit=30`, { headers: H }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/qa/pulse/latest`, { headers: H }).then(r => r.ok ? r.json() : null),
        fetch(`${API}/api/admin/sentinel/suggestions?limit=10`, { headers: H }).then(r => r.ok ? r.json() : null),
      ]);
      if (ovr.status === 'fulfilled' && ovr.value) setOverview(ovr.value);
      if (errs.status === 'fulfilled' && errs.value) setErrors(errs.value.errors || []);
      if (plz.status === 'fulfilled' && plz.value) setPulse(plz.value.run || plz.value);
      if (sug.status === 'fulfilled' && sug.value) setSuggestions(sug.value.suggestions || []);
      setLastRefresh(new Date());
    } catch { /* swallow */ }
    setBusy(false);
  }, [token]);

  // ─── auto-refresh while open (15s)
  useEffect(() => {
    if (!open || !isAdmin) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return undefined;
    }
    fetchAll();
    pollRef.current = setInterval(fetchAll, 15000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, isAdmin, fetchAll]);

  // Hide completely for non-admins
  if (!isAdmin) return null;

  // Red dot intensity — how loud should the FAB be?
  const errors24h = overview?.errors_24h ?? 0;
  const errors1h = overview?.errors_1h ?? 0;
  const pendingAi = overview?.pending_ai_suggestions ?? 0;
  const spikeAlert = (overview?.active_spikes || []).length > 0;
  const dotColor = errors1h > 5 || spikeAlert ? '#ef4444'
    : errors24h > 10 ? '#f59e0b'
    : errors24h > 0 ? '#fbbf24'
    : '#22c55e';

  // ══════════════ Render ══════════════
  return (
    <>
      {/* Floating action button — always visible for admins */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          data-testid="dev-console-fab"
          title="AUREM Dev Console · Ctrl+Shift+D"
          className="fixed bottom-5 right-5 z-[9998] flex items-center gap-2 rounded-full shadow-2xl transition hover:scale-[1.05] group"
          style={{
            background: 'linear-gradient(135deg, rgba(8,10,16,0.95), rgba(20,25,40,0.95))',
            border: `1px solid ${GOLD}55`,
            boxShadow: `0 10px 32px ${dotColor}30, 0 0 0 2px ${dotColor}22`,
            padding: '11px 16px 11px 12px',
            backdropFilter: 'blur(14px)',
          }}
        >
          <span className="relative inline-flex">
            <Bug className="w-[18px] h-[18px]" style={{ color: GOLD }} />
            <span
              className="absolute -top-1 -right-1 size-2.5 rounded-full"
              style={{ background: dotColor, boxShadow: `0 0 8px ${dotColor}` }}
            />
          </span>
          <span className="text-[10px] tracking-[2px] font-bold text-white/80 group-hover:text-white">
            DEV · {errors24h}
          </span>
        </button>
      )}

      {/* Slide-in panel */}
      {open && (
        <div
          data-testid="dev-console-panel"
          className="fixed top-4 bottom-4 right-4 z-[9999] flex flex-col rounded-2xl"
          style={{
            width: PANEL_WIDTH,
            background: 'linear-gradient(180deg, rgba(8,10,16,0.97), rgba(14,18,28,0.97))',
            border: `1px solid ${GOLD}44`,
            boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 0 1px ${GOLD}22`,
            backdropFilter: 'blur(20px)',
            animation: 'devconSlideIn 0.25s ease both',
          }}
        >
          <style>{`@keyframes devconSlideIn{from{transform:translateX(20px);opacity:0}to{transform:translateX(0);opacity:1}}`}</style>

          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${GOLD}22` }}>
            <div className="flex items-center gap-2">
              <Bug className="size-4" style={{ color: GOLD }} />
              <div>
                <div className="text-[11px] font-bold tracking-[2.5px] text-white/90">AUREM DEV CONSOLE</div>
                <div className="text-[9px] text-white/45 tracking-[1px]">
                  {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Loading…'}
                  {busy && ' · refreshing'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={fetchAll} title="Refresh"
                className="size-7 rounded-md flex items-center justify-center hover:bg-white/5 transition"
                data-testid="dev-console-refresh">
                <RefreshCw className={`size-3.5 text-white/60 ${busy ? 'animate-spin' : ''}`} />
              </button>
              <button onClick={() => setOpen(false)} title="Close (Ctrl+Shift+D)"
                className="size-7 rounded-md flex items-center justify-center hover:bg-white/5 transition"
                data-testid="dev-console-close">
                <X className="size-4 text-white/70" />
              </button>
            </div>
          </div>

          {/* KPI Strip */}
          <div className="grid grid-cols-4 gap-px px-2 pt-2 pb-2" style={{ background: 'transparent' }}>
            <KPI label="1h" value={errors1h} accent={errors1h > 5 ? '#ef4444' : GOLD} />
            <KPI label="24h" value={errors24h} accent={errors24h > 10 ? '#f59e0b' : GOLD} />
            <KPI label="AI Fixes" value={pendingAi} accent="#8b5cf6" />
            <KPI label="Spikes" value={(overview?.active_spikes || []).length} accent={spikeAlert ? '#ef4444' : GOLD} />
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-1 px-2 pt-1 pb-2" style={{ borderBottom: `1px solid ${GOLD}15` }}>
            <Tab active={tab === 'sentinel'} onClick={() => setTab('sentinel')} icon={Shield} label="Errors" badge={errors.length} testid="tab-sentinel" />
            <Tab active={tab === 'pulse'} onClick={() => setTab('pulse')} icon={Activity} label="Pulse" testid="tab-pulse" />
            <Tab active={tab === 'suggest'} onClick={() => setTab('suggest')} icon={Sparkles} label="AI Fix" badge={pendingAi} testid="tab-suggest" />
            <Tab active={tab === 'console'} onClick={() => setTab('console')} icon={Terminal} label="Console" testid="tab-console" />
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto aurem-scroll px-3 py-2">
            {tab === 'sentinel' && <SentinelTab errors={errors} />}
            {tab === 'pulse' && <PulseTab pulse={pulse} />}
            {tab === 'suggest' && <SuggestTab suggestions={suggestions} />}
            {tab === 'console' && <ConsoleTab bump={consoleBump} />}
          </div>

          {/* Footer — deep link to full views */}
          <div className="flex items-center justify-between px-3 py-2" style={{ borderTop: `1px solid ${GOLD}15` }}>
            <span className="text-[9px] tracking-[1.5px] text-white/40">Ctrl+Shift+D to toggle</span>
            <div className="flex gap-1">
              <FooterLink href="/admin/sentinel" label="Full Sentinel" />
              <FooterLink href="/admin/links" label="All Links" />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────
const KPI = ({ label, value, accent }) => (
  <div
    className="rounded-md px-2 py-1.5 flex flex-col"
    style={{ background: 'rgba(255,255,255,0.025)', border: `1px solid ${accent}22` }}
  >
    <span className="text-[8px] tracking-[1.5px] text-white/45 uppercase">{label}</span>
    <span className="text-[15px] font-black mt-0.5" style={{ color: accent }}>{value}</span>
  </div>
);

const Tab = ({ active, onClick, icon: Icon, label, badge, testid }) => (
  <button
    onClick={onClick}
    data-testid={testid}
    className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-md text-[10px] font-bold tracking-wider transition ${
      active ? 'text-black' : 'text-white/60 hover:text-white/90'
    }`}
    style={{
      background: active ? `linear-gradient(135deg, ${GOLD}, ${GOLD}cc)` : 'transparent',
    }}
  >
    <Icon className="size-3" />
    {label}
    {badge > 0 && (
      <span
        className="text-[8px] rounded-full px-1 ml-0.5"
        style={{ background: active ? '#0a0a0f' : '#ef4444', color: active ? GOLD : 'white' }}
      >
        {badge}
      </span>
    )}
  </button>
);

const FooterLink = ({ href, label }) => (
  <a
    href={href}
    target="_blank"
    rel="noreferrer"
    className="flex items-center gap-1 text-[9px] tracking-wider font-bold px-2 py-1 rounded hover:bg-white/5"
    style={{ color: GOLD }}
  >
    {label}
    <ExternalLink className="size-2.5" />
  </a>
);

// ═══════════ Sentinel Errors Tab ═══════════
const SentinelTab = ({ errors }) => {
  const [expanded, setExpanded] = useState(null);
  if (!errors || errors.length === 0) {
    return (
      <EmptyState icon={CheckCircle2} title="No errors captured" hint="Sentinel is watching — new errors will appear here live." />
    );
  }
  // Group by type
  const groups = {};
  errors.forEach(e => {
    const key = `${e.type}|${(e.message || '').slice(0, 80)}`;
    if (!groups[key]) groups[key] = { sample: e, count: 0, urls: new Set() };
    groups[key].count += 1;
    if (e.url) groups[key].urls.add(e.url);
  });
  const rows = Object.entries(groups).sort((a, b) => b[1].count - a[1].count);
  return (
    <div className="space-y-1.5">
      {rows.map(([k, g]) => {
        const e = g.sample;
        const isOpen = expanded === k;
        return (
          <div
            key={k}
            className="rounded-md p-2 cursor-pointer"
            style={{ background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)' }}
            onClick={() => setExpanded(isOpen ? null : k)}
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="size-3 mt-0.5 flex-shrink-0" style={{ color: '#ef4444' }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[9px] font-black tracking-[1px] uppercase" style={{ color: GOLD }}>
                    {e.type}
                  </span>
                  {g.count > 1 && (
                    <span className="text-[8px] bg-red-500/20 text-red-400 rounded px-1.5 py-0.5 font-bold">
                      ×{g.count}
                    </span>
                  )}
                  <span className="text-[8px] text-white/35">
                    {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : ''}
                  </span>
                </div>
                <div className="text-[10px] text-white/80 mt-0.5 leading-tight">
                  {(e.message || '').slice(0, 120) || '(no message)'}
                </div>
                {isOpen && (
                  <div className="mt-2 space-y-1.5">
                    {e.url && <KV k="URL" v={e.url} />}
                    {e.status && <KV k="Status" v={String(e.status)} />}
                    {e.stack && (
                      <div>
                        <div className="text-[8px] text-white/40 tracking-wider">STACK</div>
                        <pre className="text-[9px] text-white/70 mt-0.5 whitespace-pre-wrap font-mono bg-black/30 p-1.5 rounded max-h-40 overflow-auto">
                          {e.stack.slice(0, 800)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
              {isOpen ? <ChevronUp className="size-3 text-white/40" /> : <ChevronDown className="size-3 text-white/40" />}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ═══════════ QA Pulse Tab ═══════════
const PulseTab = ({ pulse }) => {
  if (!pulse) {
    return <EmptyState icon={Clock} title="No pulse data" hint="QA bot runs every 60s. First sweep populates shortly." />;
  }
  const checks = pulse.checks || [];
  const passed = checks.filter(c => c.passed).length;
  const failed = checks.filter(c => !c.passed).length;
  const running = checks.length - passed - failed;
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-1">
        <MiniStat label="Pass" value={passed} color="#22c55e" icon={CheckCircle2} />
        <MiniStat label="Fail" value={failed} color="#ef4444" icon={AlertTriangle} />
        <MiniStat label="Queue" value={running} color="#f59e0b" icon={Clock} />
      </div>
      <div className="space-y-1">
        {checks.slice(0, 30).map((c, i) => (
          <div
            key={i}
            className="flex items-center gap-2 px-2 py-1.5 rounded"
            style={{ background: c.passed ? 'rgba(34,197,94,0.04)' : 'rgba(239,68,68,0.06)' }}
          >
            <span className={`size-1.5 rounded-full flex-shrink-0 ${c.passed ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-[10px] text-white/80 truncate flex-1">{c.label || c.id || c.path}</span>
            <span className="text-[9px] text-white/40 font-mono">{c.status_code || '—'}</span>
            <span className="text-[9px] text-white/40 font-mono">{c.latency_ms || '—'}ms</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ═══════════ AI Suggestions Tab ═══════════
const SuggestTab = ({ suggestions }) => {
  if (!suggestions || suggestions.length === 0) {
    return <EmptyState icon={Sparkles} title="No AI suggestions yet" hint="Trigger from /admin/sentinel on any error — Claude will diagnose and propose a fix." />;
  }
  return (
    <div className="space-y-1.5">
      {suggestions.map((s) => (
        <div key={s.suggestion_id || s.id} className="rounded-md p-2"
          style={{ background: 'rgba(139,92,246,0.05)', border: '1px solid rgba(139,92,246,0.2)' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <Sparkles className="size-3" style={{ color: '#a78bfa' }} />
            <span className="text-[9px] font-bold tracking-[1px] uppercase" style={{ color: '#a78bfa' }}>
              {s.status || 'pending'}
            </span>
            <span className="text-[8px] text-white/40">{s.created_at ? new Date(s.created_at).toLocaleString() : ''}</span>
          </div>
          <div className="text-[10px] text-white/80 leading-tight">{s.summary || s.diagnosis || '(no summary)'}</div>
          {s.fix_suggestion && (
            <div className="text-[9px] text-white/60 mt-1 italic">→ {s.fix_suggestion.slice(0, 200)}</div>
          )}
        </div>
      ))}
    </div>
  );
};

// ═══════════ Browser Console Tab ═══════════
const ConsoleTab = ({ bump }) => { // eslint-disable-line no-unused-vars
  const entries = useMemo(() => [..._consoleRingBuffer].reverse(), [bump]);
  if (entries.length === 0) {
    return <EmptyState icon={Terminal} title="Console silent" hint="Browser console messages mirror here live — no F12 needed." />;
  }
  const levelColor = (lvl) => ({
    error: '#ef4444', warn: '#f59e0b', info: '#60a5fa', log: '#94a3b8',
  })[lvl] || '#94a3b8';
  return (
    <div className="space-y-0.5 font-mono">
      {entries.map((e, i) => (
        <div key={i} className="flex items-start gap-2 py-1 px-1.5 rounded text-[10px] hover:bg-white/5">
          <span className="text-white/30 flex-shrink-0" style={{ width: 55 }}>
            {e.ts.slice(11, 19)}
          </span>
          <span
            className="text-[8px] font-black uppercase flex-shrink-0 mt-0.5"
            style={{ color: levelColor(e.level), width: 38 }}
          >
            {e.level}
          </span>
          <span className="text-white/75 break-all whitespace-pre-wrap leading-tight">
            {e.msg}
          </span>
        </div>
      ))}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────
// Tiny helpers
// ─────────────────────────────────────────────────────────────────────
const EmptyState = ({ icon: Icon, title, hint }) => (
  <div className="flex flex-col items-center justify-center py-10 text-center">
    <Icon className="size-8 mb-2" style={{ color: GOLD, opacity: 0.5 }} />
    <div className="text-[11px] font-bold text-white/80">{title}</div>
    <div className="text-[9px] text-white/40 mt-1 max-w-[280px] leading-tight">{hint}</div>
  </div>
);

const MiniStat = ({ label, value, color, icon: Icon }) => (
  <div className="rounded px-2 py-1.5 flex items-center gap-1.5" style={{ background: `${color}10` }}>
    <Icon className="size-3" style={{ color }} />
    <div className="flex flex-col">
      <span className="text-[8px] text-white/50 uppercase tracking-wider">{label}</span>
      <span className="text-[12px] font-black" style={{ color }}>{value}</span>
    </div>
  </div>
);

const KV = ({ k, v }) => (
  <div className="flex items-start gap-2 text-[9px]">
    <span className="text-white/35 uppercase tracking-wider w-14 flex-shrink-0">{k}</span>
    <span className="text-white/75 break-all font-mono">{v}</span>
  </div>
);
