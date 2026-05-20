/**
 * AdminShortcuts — Iteration 214
 * ==============================
 * Notion/Linear-style keyboard shortcuts + command palette for all admin pages.
 *
 * Shortcuts:
 *   /          — focus universal search (opens palette)
 *   Cmd/Ctrl-K — same (opens palette)
 *   ESC        — close palette
 *   g then b   — go to Builder (Control Center)
 *   g then e   — go to Evolver
 *   g then c   — go to Control Center
 *   g then s   — go to System Overview
 *   g then m   — go to Mission Control
 *   g then l   — go to Impersonation Log
 *   g then i   — go to Business IDs
 *   g then d   — go to Dashboard
 *   ?          — show the shortcut help card
 *
 * Palette understands:
 *   • email        → /admin/customer/{email}
 *   • BIN format   → /admin/customer/{BIN}  (e.g. RERO-DMYE)
 *   • build_id 12h → /admin/builder/{id}    (12-hex chars)
 *   • gene_id 12h  → /admin/evolver?highlight={id}
 *   • free text    → /admin/customer/{encoded}
 */
import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';
import { useNavigate, useLocation } from 'react-router-dom';

const C = {
  bg: 'rgba(6,6,12,0.85)', panel: '#0D0D17', border: 'rgba(212,175,55,0.22)',
  accent: '#D4AF37', text: '#E8E0D0', textD: '#8A8070', dim: '#5A5468',
};

const QUICK_NAV = [
  // ── Cockpit ───────────────────────────────────────────
  { id: 'mc',       label: 'Mission Control',           hint: 'g m', href: '/admin/mission-control' },
  { id: 'cc',       label: 'Control Center',            hint: 'g c', href: '/admin/control-center' },
  { id: 'sys',      label: 'System Overview',           hint: 'g s', href: '/admin/system-overview' },
  { id: 'pulse',    label: 'System Pulse · Live',       hint: 'g p', href: '/admin/system-pulse-live' },
  { id: 'blocks',   label: 'Pillar Status Blocks',      hint: 'g B', href: '/admin/blocks' },

  // ── Sovereign / Money ─────────────────────────────────
  { id: 'board',    label: 'Sovereign Boardroom · P&L', hint: 'g r', href: '/admin/boardroom' },
  { id: 'plans',    label: 'Plans · Pricing',           hint: '',    href: '/admin/plans' },
  { id: 'analytics',label: 'Analytics Dashboard',       hint: 'g a', href: '/admin/analytics' },
  { id: 'bids',     label: 'Business IDs',              hint: 'g i', href: '/admin/business-ids' },
  { id: 'imp',      label: 'Impersonation Log',         hint: 'g l', href: '/admin/impersonation-log' },

  // ── Intelligence ──────────────────────────────────────
  { id: 'rcmd',     label: 'Root Command · Errors',     hint: 'g r', href: '/admin/root-command' },
  { id: 'pmap',     label: 'Pillars Map',               hint: '',    href: '/admin/pillars-map' },
  { id: 'brain',    label: 'Brain Graph',               hint: '',    href: '/admin/brain-graph' },
  { id: 'vang',     label: 'Vanguard',                  hint: '',    href: '/admin/vanguard' },
  { id: 'links',    label: 'Links Hub',                 hint: '',    href: '/admin/links' },

  // ── Health / Self-Heal ────────────────────────────────
  { id: 'sentinel', label: 'Sentinel · Client Errors',  hint: 'g x', href: '/admin/sentinel' },
  { id: 'fixer',    label: 'Auto-Fixer · Repairs',      hint: 'g f', href: '/admin/auto-fixer' },
  { id: 'stem',     label: 'Stem-Fix · Refactor',       hint: '',    href: '/admin/stem-fix' },
  { id: 'self',     label: 'Self-Repair Console',       hint: '',    href: '/admin/self-repair' },
  { id: 'evo',      label: 'EvoMap Evolver',            hint: 'g e', href: '/admin/evolver' },
  { id: 'fang',     label: 'OpenFang · Lead Hand',      hint: 'g o', href: '/admin/openfang' },
  { id: 'audit',    label: 'System Audit',              hint: '',    href: '/admin/system-audit' },
  { id: 'wire',     label: 'Wiring Audit',              hint: '',    href: '/admin/wiring-audit' },

  // ── Outreach ──────────────────────────────────────────
  { id: 'sitemon',  label: 'Site Monitor · Admin',      hint: '',    href: '/admin/site-monitor' },
  { id: 'httest',   label: 'Hunter · Live Test',        hint: 'g h', href: '/admin/hunter-test' },
  { id: 'case',     label: 'Case Study Builder',        hint: 'g k', href: '/admin/case-study' },

  // ── Settings ──────────────────────────────────────────
  { id: '2fa',      label: '2FA Enrolment',             hint: '',    href: '/admin/2fa' },

  // ── Out of admin ──────────────────────────────────────
  { id: 'dash',     label: 'Customer Dashboard ↗',      hint: 'g d', href: '/dashboard' },
  { id: 'leads',    label: 'Leads ↗',                   hint: '',    href: '/leads' },
];

const HEX12 = /^[a-f0-9]{12}$/i;
const BIN_RE = /^[A-Z]{3,4}[\s-]?[A-Z]{3,4}$/i;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function resolveQuery(raw) {
  const q = (raw || '').trim();
  if (!q) return null;
  if (EMAIL_RE.test(q)) return `/admin/customer/${encodeURIComponent(q)}`;
  if (BIN_RE.test(q))   return `/admin/customer/${encodeURIComponent(q)}`;
  if (HEX12.test(q))    return `/admin/builder/${q.toLowerCase()}`;
  // fallback: treat free text as a customer identifier
  return `/admin/customer/${encodeURIComponent(q)}`;
}

export default function AdminShortcuts() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [gArmed, setGArmed] = useState(false);
  const gTimerRef = useRef(null);
  const [showHelp, setShowHelp] = useState(false);
  const inputRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();
  const { pathname } = location;

  // Only activate on admin routes
  const isAdmin = useMemo(
    () => pathname.startsWith('/admin') || pathname === '/dashboard' || pathname === '/leads',
    [pathname],
  );

  const armG = useCallback(() => {
    setGArmed(true);
    if (gTimerRef.current) clearTimeout(gTimerRef.current);
    gTimerRef.current = setTimeout(() => setGArmed(false), 1200);
  }, []);

  // Global shortcuts — only when no input is focused
  useHotkeys('/', (e) => {
    if (!isAdmin) return;
    const t = e.target;
    if (t && ['INPUT', 'TEXTAREA'].includes(t.tagName)) return;
    e.preventDefault();
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 10);
  }, { enableOnFormTags: false }, [isAdmin]);

  useHotkeys('mod+k', (e) => {
    if (!isAdmin) return;
    e.preventDefault();
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 10);
  }, { enableOnFormTags: true }, [isAdmin]);

  // External trigger (e.g. AdminShell sidebar Search button)
  useEffect(() => {
    const onOpen = () => {
      if (!isAdmin) return;
      setOpen(true);
      setTimeout(() => inputRef.current?.focus(), 10);
    };
    window.addEventListener('aurem:open-palette', onOpen);
    return () => window.removeEventListener('aurem:open-palette', onOpen);
  }, [isAdmin]);

  useHotkeys('escape', () => {
    setOpen(false);
    setShowHelp(false);
    setGArmed(false);
  }, { enableOnFormTags: true });

  useHotkeys('shift+/', (e) => {
    if (!isAdmin) return;
    const t = e.target;
    if (t && ['INPUT', 'TEXTAREA'].includes(t.tagName)) return;
    e.preventDefault();
    setShowHelp((s) => !s);
  }, [isAdmin]);

  useHotkeys('g', (e) => {
    if (!isAdmin) return;
    const t = e.target;
    if (t && ['INPUT', 'TEXTAREA'].includes(t.tagName)) return;
    armG();
  }, [isAdmin, armG]);

  const gMap = {
    b: '/admin/boardroom',          // g b → Boardroom (rebound from Builder)
    e: '/admin/evolver',
    c: '/admin/control-center',
    s: '/admin/system-overview',
    m: '/admin/mission-control',
    l: '/admin/impersonation-log',
    i: '/admin/business-ids',
    d: '/dashboard',
    o: '/admin/openfang',
    x: '/admin/sentinel',
    k: '/admin/case-study',
    h: '/admin/hunter-test',
    p: '/admin/system-pulse-live',
    r: '/admin/root-command',       // g r → Root Command
    f: '/admin/auto-fixer',         // g f → Fixer
    a: '/admin/analytics',          // g a → Analytics
  };

  // Register each g-letter shortcut.
  Object.keys(gMap).forEach((k) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useHotkeys(k, (e) => {
      if (!isAdmin || !gArmed) return;
      const t = e.target;
      if (t && ['INPUT', 'TEXTAREA'].includes(t.tagName)) return;
      e.preventDefault();
      setGArmed(false);
      navigate(gMap[k]);
    }, [isAdmin, gArmed, navigate]);
  });

  const submit = (e) => {
    e?.preventDefault?.();
    const dest = resolveQuery(query);
    if (!dest) return;
    setOpen(false);
    setQuery('');
    navigate(dest);
  };

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return QUICK_NAV;
    return QUICK_NAV.filter((x) =>
      x.label.toLowerCase().includes(q) || x.id.includes(q) || x.hint.includes(q),
    );
  }, [query]);

  if (!isAdmin) return null;

  return (
    <>
      {/* G-armed hint bubble */}
      {gArmed && (
        <div data-testid="shortcut-g-hint" style={{
          position: 'fixed', bottom: 18, left: 18, zIndex: 9998,
          background: C.panel, border: `1px solid ${C.border}`, borderRadius: 10,
          padding: '8px 14px', color: C.accent, fontFamily: "'JetBrains Mono',monospace",
          fontSize: 11, letterSpacing: '0.1em', boxShadow: '0 4px 18px rgba(0,0,0,0.4)',
        }}>
          g… → press <strong>b e c s m l i d</strong>
        </div>
      )}

      {/* Help overlay */}
      {showHelp && (
        <div data-testid="shortcut-help" onClick={() => setShowHelp(false)} style={{
          position: 'fixed', inset: 0, zIndex: 9999, background: C.bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backdropFilter: 'blur(6px)', fontFamily: "'Jost',sans-serif",
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: 520, maxWidth: 'calc(100% - 36px)', background: C.panel,
            border: `1px solid ${C.border}`, borderRadius: 16, padding: '22px 26px',
            color: C.text,
          }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: C.accent, letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 16 }}>
              Keyboard Shortcuts
            </div>
            {[
              ['/',          'Open command palette'],
              ['Cmd/Ctrl-K', 'Open command palette'],
              ['g b',        'Sovereign Boardroom · P&L'],
              ['g r',        'Root Command · Errors'],
              ['g f',        'Auto-Fixer · Repairs'],
              ['g e',        'EvoMap Evolver'],
              ['g c',        'Control Center'],
              ['g s',        'System Overview'],
              ['g p',        'System Pulse · Live'],
              ['g m',        'Mission Control'],
              ['g a',        'Analytics'],
              ['g x',        'Sentinel · Client Errors'],
              ['g h',        'Hunter · Live Test'],
              ['g k',        'Case Study Builder'],
              ['g o',        'OpenFang · Lead Hand'],
              ['g l',        'Impersonation Log'],
              ['g i',        'Business IDs'],
              ['g d',        'Customer Dashboard'],
              ['?',          'Toggle this help card'],
              ['ESC',        'Close modal / palette / help'],
            ].map(([k, v]) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', fontSize: 12 }}>
                <span style={{ color: C.text }}>{v}</span>
                <code style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 11, padding: '3px 10px', borderRadius: 6, background: 'rgba(212,175,55,0.08)', border: `1px solid ${C.border}`, color: C.accent }}>{k}</code>
              </div>
            ))}
            <div style={{ marginTop: 14, fontSize: 11, color: C.textD, lineHeight: 1.6 }}>
              Palette resolves: emails, BINs (e.g. <code style={{ color: C.accent }}>RERO-DMYE</code>), 12-hex build_ids, or any identifier.
            </div>
          </div>
        </div>
      )}

      {/* Command palette */}
      {open && (
        <div data-testid="shortcut-palette" onClick={() => setOpen(false)} style={{
          position: 'fixed', inset: 0, zIndex: 9999, background: C.bg,
          backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'flex-start',
          justifyContent: 'center', paddingTop: '12vh', fontFamily: "'Jost',sans-serif",
        }}>
          <form onSubmit={submit} onClick={(e) => e.stopPropagation()} style={{
            width: 560, maxWidth: 'calc(100% - 36px)', background: C.panel,
            border: `1px solid ${C.border}`, borderRadius: 16, padding: '16px 18px',
            boxShadow: '0 20px 48px rgba(0,0,0,0.6)', color: C.text,
          }}>
            <input
              data-testid="shortcut-input"
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search… email · BIN · build_id · gene_id · page"
              autoFocus
              style={{
                width: '100%', padding: '12px 14px', background: 'rgba(0,0,0,0.3)',
                border: `1px solid ${C.border}`, borderRadius: 10, color: C.text,
                fontSize: 14, fontFamily: "'Jost',sans-serif", outline: 'none',
              }}
            />
            <div style={{ fontSize: 10, letterSpacing: '0.18em', textTransform: 'uppercase', color: C.dim, margin: '14px 4px 8px' }}>
              Jump to
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 320, overflowY: 'auto' }}>
              {matches.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  data-testid={`shortcut-nav-${m.id}`}
                  onClick={() => { setOpen(false); setQuery(''); navigate(m.href); }}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '9px 12px', background: 'transparent', border: `1px solid transparent`,
                    borderRadius: 8, color: C.text, fontSize: 13, fontFamily: "'Jost',sans-serif",
                    cursor: 'pointer', textAlign: 'left',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(212,175,55,0.06)'; e.currentTarget.style.borderColor = C.border; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}
                >
                  <span>{m.label}</span>
                  {m.hint && (
                    <code style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'rgba(212,175,55,0.08)', color: C.accent }}>
                      {m.hint}
                    </code>
                  )}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 10, color: C.dim, marginTop: 12, display: 'flex', justifyContent: 'space-between' }}>
              <span>Press ENTER to open</span>
              <span>?  for all shortcuts</span>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
