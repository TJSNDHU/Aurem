/**
 * LuxeDashboardPreview — frame-to-frame match of user's 8K reference.
 * Route: /preview/luxe-dashboard
 *
 * This is a PREVIEW ONLY page. It does not replace /my or /dashboard.
 * Once approved, we'll lift it into CustomerPortal.jsx.
 *
 * Auth-mapping toggles integrated:
 *   - BIN switcher (top-right card)
 *   - FaceID Auth toggle
 *   - 2FA Enabled toggle
 *   - Session Monitoring toggle
 *   - Customer | Admin top-of-window mode toggle
 */

import React, { useMemo, useState } from 'react';
import {
  Home, Folder, Shield, User, Settings, LogOut,
  Bell, ChevronDown, KeyRound, Check, Sparkles, ChevronsUpDown,
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  XAxis, YAxis, Tooltip, RadialBarChart, RadialBar,
} from 'recharts';

// ─── tokens ────────────────────────────────────────────────────────────
const GOLD = '#D4A373';
const GOLD_HI = '#F7E7CE';
const GOLD_DK = '#8B6F44';
const INK = '#0A0A0F';
const PANEL = 'rgba(22,24,28,0.55)';
const PANEL_HI = 'rgba(36,38,44,0.45)';
const STROKE = 'rgba(212,163,115,0.18)';
const TEXT_HI = '#E8E4DE';
const TEXT_MD = '#9A9590';
const TEXT_LO = '#6A6560';

const fontDisplay = "'Cinzel', 'Montserrat', serif";
const fontBody = "'Jost', 'Inter', system-ui, sans-serif";
const fontMono = "'JetBrains Mono', ui-monospace, monospace";

// ─── mock data ─────────────────────────────────────────────────────────
const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug'];
const wave = months.map((m, i) => {
  const t = i / (months.length - 1);
  return {
    m,
    a: Math.round(8000 + 12000 * Math.sin(i * 0.7) + 7000 * t),
    b: Math.round(15000 + 9000 * Math.cos(i * 0.6) + 12000 * t),
    c: Math.round(22000 + 8000 * Math.sin(i * 1.1 + 1) + 14000 * t),
    d: Math.round(28000 + 7000 * Math.cos(i * 0.9 + 0.3) + 10000 * t),
  };
});
const activeUsers = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.slice(0, 26).split('').map((k, i) => ({
  k, v: Math.round(20 + 60 * Math.abs(Math.sin(i * 0.7))) + (i % 4 === 0 ? 30 : 0),
}));
const revBin = Array.from({ length: 13 }).map((_, i) => ({
  x: i, y: Math.round(80 + 220 * (i / 12) + 30 * Math.sin(i * 1.2)),
}));
const alerts = [
  { t: '10:58 PM', sev: 'HIGH', label: 'FaceID auth retry' },
  { t: '10:53 PM', sev: 'MED',  label: 'Brief device fingerprint shift' },
  { t: '07:23 PM', sev: 'LOW',  label: 'Brief geo anomaly resolved' },
  { t: '07:23 PM', sev: 'LOW',  label: 'Brief geo anomaly resolved' },
  { t: '10:23 PM', sev: 'LOW',  label: 'Security policy reviewed' },
  { t: '10:38 PM', sev: 'LOW',  label: 'Session token rotated' },
];
const sevColor = {
  HIGH: { bg: 'rgba(220,38,38,0.18)', fg: '#fca5a5' },
  MED:  { bg: 'rgba(234,88,12,0.18)', fg: '#fdba74' },
  LOW:  { bg: 'rgba(120,140,90,0.18)', fg: '#bef264' },
};

const bins = [
  { bin: 'AURE-8829', card: '1234 5678 9900', status: 'ACTIVE' },
  { bin: 'RERO-3DEJ', card: '4111 2244 6655', status: 'ACTIVE' },
  { bin: 'POLA-7K2X', card: '5500 0099 1188', status: 'PAUSED' },
];

// ─── primitives ────────────────────────────────────────────────────────
const Glass = ({ children, style, className = '', ...rest }) => (
  <div
    className={className}
    style={{
      background: `linear-gradient(155deg, ${PANEL} 0%, rgba(14,16,20,0.55) 55%, ${PANEL_HI} 100%)`,
      border: `1px solid ${STROKE}`,
      borderRadius: 22,
      backdropFilter: 'blur(28px) saturate(160%)',
      WebkitBackdropFilter: 'blur(28px) saturate(160%)',
      boxShadow: '0 30px 80px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)',
      position: 'relative',
      overflow: 'hidden',
      ...style,
    }}
    {...rest}
  >
    {/* sheen */}
    <div aria-hidden style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background:
        'radial-gradient(120% 60% at 50% 0%, rgba(212,163,115,0.08) 0%, transparent 55%),' +
        'radial-gradient(80% 50% at 10% 100%, rgba(247,231,206,0.04) 0%, transparent 60%)',
      borderRadius: 'inherit',
    }} />
    <div style={{ position: 'relative', zIndex: 1, height: '100%' }}>{children}</div>
  </div>
);

const Pill = ({ on = true, children }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 10px', borderRadius: 999,
    background: on ? 'rgba(74,222,128,0.14)' : 'rgba(220,38,38,0.14)',
    color: on ? '#86efac' : '#fca5a5',
    fontFamily: fontMono, fontSize: 10, letterSpacing: '0.18em',
    border: `1px solid ${on ? 'rgba(74,222,128,0.28)' : 'rgba(220,38,38,0.28)'}`,
  }}>
    {children}
  </span>
);

const DotMatrix = ({ rows = 2, cols = 12 }) => (
  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 3 }}>
    {Array.from({ length: rows * cols }).map((_, i) => (
      <span key={i} style={{
        width: 3, height: 3, borderRadius: '50%',
        background: i % 7 === 0 ? GOLD_HI : i % 3 === 0 ? GOLD : 'rgba(212,163,115,0.25)',
      }} />
    ))}
  </div>
);

const Toggle = ({ on, onChange, label, testid }) => (
  <button
    type="button"
    data-testid={testid}
    onClick={() => onChange(!on)}
    style={{
      display: 'flex', alignItems: 'center', gap: 12, width: '100%',
      background: 'transparent', border: 'none', cursor: 'pointer',
      padding: '8px 0', textAlign: 'left',
    }}
  >
    <span style={{
      width: 22, height: 22, borderRadius: '50%',
      background: on ? `linear-gradient(135deg, ${GOLD}, ${GOLD_DK})` : 'rgba(255,255,255,0.05)',
      border: `1px solid ${on ? 'rgba(247,231,206,0.45)' : 'rgba(255,255,255,0.12)'}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      transition: 'all .25s ease',
      boxShadow: on ? `0 0 14px rgba(212,163,115,0.45)` : 'none',
    }}>
      {on && <Check size={13} color={INK} strokeWidth={3} />}
    </span>
    <span style={{ fontFamily: fontBody, fontSize: 13, color: TEXT_HI, letterSpacing: '0.02em' }}>
      {label}
    </span>
  </button>
);

// ─── sidebar ───────────────────────────────────────────────────────────
const Sidebar = ({ active, onChange }) => {
  const items = [
    { k: 'home',     i: Home,     l: 'Home' },
    { k: 'bins',     i: Folder,   l: 'BINs' },
    { k: 'security', i: Shield,   l: 'Security' },
    { k: 'profile',  i: User,     l: 'Profile' },
    { k: 'settings', i: Settings, l: 'Settings' },
  ];
  return (
    <aside style={{
      width: 116, flexShrink: 0,
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      paddingTop: 28, paddingBottom: 24,
      borderRight: `1px solid ${STROKE}`,
    }}>
      <div style={{ textAlign: 'center', marginBottom: 36 }}>
        <div style={{
          fontFamily: fontDisplay, color: GOLD_HI, letterSpacing: '0.2em',
          fontSize: 14, fontWeight: 700,
        }}>AUREM</div>
        <div style={{
          fontFamily: fontBody, color: TEXT_LO, letterSpacing: '0.18em',
          fontSize: 8, marginTop: 4,
        }}>BUSINESS ORA</div>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
        {items.map(({ k, i: Icon, l }) => {
          const on = active === k;
          return (
            <button
              key={k}
              data-testid={`sidenav-${k}`}
              onClick={() => onChange(k)}
              style={{
                position: 'relative',
                width: 64, padding: '14px 0',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: on ? GOLD_HI : TEXT_MD,
                transition: 'color .25s',
              }}
            >
              {on && <span style={{
                position: 'absolute', left: -32, top: 8, bottom: 8, width: 3,
                borderRadius: 4, background: `linear-gradient(180deg, ${GOLD_HI}, ${GOLD})`,
                boxShadow: `0 0 12px ${GOLD}`,
              }} />}
              <Icon size={20} strokeWidth={1.6} />
              <span style={{ fontFamily: fontBody, fontSize: 11, letterSpacing: '0.05em' }}>{l}</span>
            </button>
          );
        })}
      </nav>

      <button data-testid="sidenav-logout" style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        color: TEXT_MD, padding: 10, marginTop: 10,
      }}>
        <LogOut size={18} strokeWidth={1.6} />
      </button>
    </aside>
  );
};

// ─── header BIN chip (replaces floating BIN card; lives in TopHeader) ──
const BinChip = ({ active, options, onSwitch }) => {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        data-testid="header-bin-chip"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 14px', borderRadius: 999,
          background: 'rgba(20,20,24,0.7)',
          border: `1px solid rgba(212,163,115,0.30)`,
          color: GOLD_HI, fontFamily: fontBody, fontSize: 12,
          letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700,
          cursor: 'pointer', transition: 'all .25s',
        }}
      >
        <KeyRound size={13} color={GOLD} />
        BIN:&nbsp;<span style={{ color: GOLD_HI }}>{active.bin}</span>
        <ChevronsUpDown size={12} color={TEXT_MD} />
      </button>

      {open && (
        <Glass style={{
          position: 'absolute', right: 0, top: 'calc(100% + 8px)',
          width: 280, padding: 8, zIndex: 60,
        }}>
          <div style={{
            fontFamily: fontBody, fontSize: 10, color: TEXT_MD,
            letterSpacing: '0.18em', textTransform: 'uppercase',
            padding: '8px 12px',
          }}>
            Switch BIN
          </div>
          {options.map((b) => (
            <button
              key={b.bin}
              data-testid={`bin-option-${b.bin}`}
              onClick={() => { onSwitch(b); setOpen(false); }}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                width: '100%', padding: '10px 12px', borderRadius: 10,
                background: b.bin === active.bin ? 'rgba(212,163,115,0.10)' : 'transparent',
                border: 'none', cursor: 'pointer', textAlign: 'left',
                color: TEXT_HI, fontFamily: fontBody, fontSize: 12,
              }}
            >
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ color: GOLD_HI, fontWeight: 600 }}>{b.bin}</span>
                <span style={{ color: TEXT_MD, fontFamily: fontMono, fontSize: 10 }}>{b.card}</span>
              </span>
              <Pill on={b.status === 'ACTIVE'}>{b.status}</Pill>
            </button>
          ))}
        </Glass>
      )}
    </div>
  );
};

// ─── header customer-name chip ─────────────────────────────────────────
const CustomerChip = ({ name }) => (
  <span
    data-testid="header-customer-chip"
    style={{
      display: 'inline-flex', alignItems: 'center', gap: 8,
      padding: '7px 14px', borderRadius: 999,
      background: `linear-gradient(135deg, ${GOLD} 0%, ${GOLD_DK} 100%)`,
      color: INK, fontFamily: fontBody, fontSize: 12,
      letterSpacing: '0.16em', textTransform: 'uppercase', fontWeight: 700,
      border: `1px solid rgba(247,231,206,0.4)`,
      boxShadow: '0 4px 18px rgba(212,163,115,0.32)',
    }}
  >
    <User size={13} color={INK} strokeWidth={2.4} />
    {name}
  </span>
);

// ─── header Account Security button + dropdown popover ────────────────
const SecurityHeaderButton = ({ score, faceid, twofa, session, onToggle }) => {
  const [open, setOpen] = useState(false);
  const data = [{ name: 'sec', value: score, fill: 'url(#secGradMini)' }];
  return (
    <div style={{ position: 'relative' }}>
      <button
        type="button"
        data-testid="security-header-btn"
        onClick={() => setOpen((o) => !o)}
        style={{
          position: 'relative', width: 40, height: 40, borderRadius: 12,
          background: PANEL, border: `1px solid ${STROKE}`,
          color: GOLD_HI, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all .25s',
        }}
        title={`Account Security — ${score}%`}
      >
        <Shield size={16} />
        <span style={{
          position: 'absolute', bottom: -4, right: -4,
          minWidth: 22, height: 16, padding: '0 4px',
          borderRadius: 8,
          background: `linear-gradient(135deg, ${GOLD_HI}, ${GOLD_DK})`,
          color: INK, fontFamily: fontMono, fontSize: 9, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 10px rgba(212,163,115,0.4)',
        }}>
          {score}
        </span>
      </button>

      {open && (
        <Glass
          data-testid="security-popover"
          style={{
            position: 'absolute', right: 0, top: 'calc(100% + 10px)',
            width: 280, padding: 18, zIndex: 60,
          }}
        >
          <div style={{
            fontFamily: fontDisplay, color: GOLD_HI, fontSize: 11,
            letterSpacing: '0.22em', textTransform: 'uppercase',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            Account Security
            <button
              data-testid="security-popover-close"
              onClick={() => setOpen(false)}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: TEXT_MD, fontSize: 14, padding: 0, lineHeight: 1,
              }}
            >×</button>
          </div>

          <div style={{
            display: 'flex', alignItems: 'center', gap: 14, marginTop: 12,
          }}>
            <div style={{ position: 'relative', width: 92, height: 92, flexShrink: 0 }}>
              <ResponsiveContainer>
                <RadialBarChart innerRadius="74%" outerRadius="100%" data={data} startAngle={90} endAngle={-270}>
                  <defs>
                    <linearGradient id="secGradMini" x1="0" x2="1" y1="0" y2="1">
                      <stop offset="0%" stopColor={GOLD_HI} />
                      <stop offset="100%" stopColor={GOLD_DK} />
                    </linearGradient>
                  </defs>
                  <RadialBar background={{ fill: 'rgba(255,255,255,0.04)' }} dataKey="value" cornerRadius={6} />
                </RadialBarChart>
              </ResponsiveContainer>
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
              }}>
                <div style={{ fontFamily: fontDisplay, fontSize: 22, color: TEXT_HI, fontWeight: 700, letterSpacing: '-0.02em' }}>
                  {score}%
                </div>
                <div style={{ fontFamily: fontBody, fontSize: 8, color: TEXT_MD, letterSpacing: '0.25em' }}>
                  SECURE
                </div>
              </div>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Toggle on={faceid}  onChange={(v) => onToggle('faceid', v)}  label="FaceID Auth"        testid="toggle-faceid" />
              <Toggle on={twofa}   onChange={(v) => onToggle('twofa', v)}   label="2FA Enabled"        testid="toggle-2fa" />
              <Toggle on={session} onChange={(v) => onToggle('session', v)} label="Session Monitoring" testid="toggle-session" />
            </div>
          </div>
        </Glass>
      )}
    </div>
  );
};

// ─── center: hero stats + wave chart ───────────────────────────────────
const HeroChart = () => {
  const annotations = [
    { x: 1, y: 23000, label: 'Furnikas',     value: '+32.8k' },
    { x: 2, y: 11000, label: 'Lnitnaxtring', value: '+5.3k'  },
    { x: 4, y: 36000, label: 'Businessers',  value: '+92.8k' },
    { x: 5, y: 29000, label: 'Light weight', value: '+35.8k' },
    { x: 7, y: 41000, label: 'Biowtly state',value: '+83.3k' },
  ];

  // Generate dense wavy data for organic flow look (not just monthly)
  const dense = useMemo(() => {
    const arr = [];
    for (let i = 0; i <= 70; i += 1) {
      const t = i / 70;
      const monthIdx = t * (months.length - 1);
      const m = months[Math.round(monthIdx)];
      arr.push({
        i,
        m: i % 10 === 0 ? m : '',
        a: 6000 + 14000 * Math.sin(i * 0.18) + 9000 * t + 1500 * Math.sin(i * 0.42),
        b: 12000 + 11000 * Math.sin(i * 0.15 + 1.2) + 12000 * t + 1500 * Math.cos(i * 0.34),
        c: 18000 + 9000 * Math.sin(i * 0.13 + 2.1) + 13000 * t + 1500 * Math.sin(i * 0.27 + 0.6),
        d: 24000 + 8000 * Math.sin(i * 0.11 + 0.6) + 11000 * t + 1500 * Math.cos(i * 0.29 + 1.1),
        e: 9000  + 13000 * Math.cos(i * 0.16 + 0.9) + 8000  * t + 1500 * Math.sin(i * 0.31),
      });
    }
    return arr;
  }, []);

  return (
    <div style={{ position: 'relative', height: 360 }}>
      <ResponsiveContainer>
        <LineChart data={dense} margin={{ top: 30, right: 24, left: 4, bottom: 8 }}>
          <XAxis
            dataKey="i" tickLine={false} axisLine={false}
            ticks={[0, 10, 20, 30, 40, 50, 60, 70]}
            tickFormatter={(v) => months[Math.min(Math.round(v / 10), months.length - 1)] || ''}
            tick={{ fill: TEXT_MD, fontFamily: fontBody, fontSize: 11 }}
          />
          <YAxis
            tickLine={false} axisLine={false}
            tick={{ fill: TEXT_LO, fontFamily: fontBody, fontSize: 11 }}
            tickFormatter={(v) => `${Math.round(v / 1000)}k`}
            ticks={[0, 10000, 20000, 30000, 40000]}
            domain={[0, 45000]}
          />
          <Tooltip
            cursor={{ stroke: GOLD, strokeOpacity: 0.3, strokeWidth: 1 }}
            contentStyle={{
              background: 'rgba(15,15,18,0.92)', border: `1px solid ${STROKE}`,
              borderRadius: 10, color: TEXT_HI, fontFamily: fontMono, fontSize: 11,
            }}
            labelStyle={{ color: GOLD_HI }}
          />
          {/* multi-stream organic wave lines, no fills */}
          <Line type="monotone" dataKey="a" stroke="#5a4f3e" strokeWidth={1}   dot={false} strokeDasharray="2 2" />
          <Line type="monotone" dataKey="e" stroke="#a36d4a" strokeWidth={1.2} dot={false} strokeOpacity={0.85} />
          <Line type="monotone" dataKey="b" stroke={GOLD_DK} strokeWidth={1.5} dot={false} />
          <Line type="monotone" dataKey="c" stroke={GOLD}    strokeWidth={1.8} dot={false} />
          <Line type="monotone" dataKey="d" stroke={GOLD_HI} strokeWidth={2.2} dot={false} />
        </LineChart>
      </ResponsiveContainer>

      {/* annotations layer (absolute) */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {annotations.map((a, i) => {
          const left = `${(a.x / 7) * 90 + 5}%`;
          const top = `${100 - (a.y / 45000) * 80 - 6}%`;
          return (
            <div key={i} style={{
              position: 'absolute', left, top,
              transform: 'translate(-50%, -100%)',
              textAlign: 'center',
              fontFamily: fontBody,
            }}>
              <div style={{ fontSize: 11, color: TEXT_MD, letterSpacing: '0.04em' }}>{a.label}</div>
              <div style={{ fontFamily: fontDisplay, fontSize: 14, color: GOLD_HI, fontWeight: 600 }}>{a.value}</div>
              <span style={{
                display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                background: GOLD_HI, boxShadow: `0 0 12px ${GOLD_HI}`, marginTop: 4,
              }} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ─── bottom cards ──────────────────────────────────────────────────────
const ActiveUsersCard = () => (
  <Glass style={{ padding: 22, height: 220 }}>
    <div style={{ fontFamily: fontDisplay, color: GOLD_HI, letterSpacing: '0.18em', fontSize: 12, textTransform: 'uppercase' }}>
      Active Users
    </div>
    <div style={{ height: 130, marginTop: 14 }}>
      <ResponsiveContainer>
        <BarChart data={activeUsers} margin={{ top: 8, right: 0, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={GOLD_HI} />
              <stop offset="100%" stopColor={GOLD_DK} stopOpacity={0.5} />
            </linearGradient>
            <linearGradient id="barGrey" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7a7a82" />
              <stop offset="100%" stopColor="#3a3a40" stopOpacity={0.5} />
            </linearGradient>
          </defs>
          <XAxis dataKey="k" tickLine={false} axisLine={false}
            tick={{ fill: TEXT_LO, fontFamily: fontMono, fontSize: 9 }} interval={3} />
          <YAxis hide />
          <Bar dataKey="v" radius={[2, 2, 0, 0]}
            fill="url(#barGrad)"
            shape={(props) => {
              const isAccent = props.index % 5 === 0 || props.index % 7 === 0;
              return (
                <rect
                  x={props.x} y={props.y} width={props.width} height={props.height}
                  rx={2} ry={2}
                  fill={isAccent ? 'url(#barGrad)' : 'url(#barGrey)'}
                />
              );
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      fontFamily: fontMono, fontSize: 10, color: TEXT_LO, marginTop: -6,
    }}>
      <span>A</span><span>D</span>
    </div>
  </Glass>
);

const RevenueByBinCard = () => (
  <Glass style={{ padding: 22, height: 220 }}>
    <div style={{ fontFamily: fontDisplay, color: GOLD_HI, letterSpacing: '0.18em', fontSize: 12, textTransform: 'uppercase' }}>
      Revenue by BIN
    </div>
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, marginTop: 14 }}>
      <div style={{ minWidth: 84 }}>
        <div style={{ fontFamily: fontDisplay, fontSize: 38, color: TEXT_HI, fontWeight: 700, lineHeight: 1 }}>290</div>
        <div style={{ fontFamily: fontBody, fontSize: 10, color: TEXT_MD, letterSpacing: '0.2em', marginTop: 4 }}>REVENUE</div>
      </div>
      <div style={{ flex: 1, height: 120 }}>
        <ResponsiveContainer>
          <LineChart data={revBin} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={GOLD_DK} />
                <stop offset="100%" stopColor={GOLD_HI} />
              </linearGradient>
            </defs>
            <XAxis dataKey="x" hide />
            <YAxis hide />
            <Line type="monotone" dataKey="y" stroke="url(#lineGrad)" strokeWidth={2.4} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
    <div style={{
      display: 'flex', justifyContent: 'space-between',
      fontFamily: fontMono, fontSize: 10, color: TEXT_LO, marginTop: 4,
    }}>
      <span>0</span><span>12</span>
    </div>
  </Glass>
);

const SecurityAlertsCard = () => (
  <Glass style={{ padding: 22, height: 220 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div style={{ fontFamily: fontDisplay, color: GOLD_HI, letterSpacing: '0.18em', fontSize: 12, textTransform: 'uppercase' }}>
        Security Alerts
      </div>
    </div>
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginTop: 8 }}>
      <div style={{ minWidth: 50 }}>
        <div style={{ fontFamily: fontDisplay, fontSize: 38, color: TEXT_HI, fontWeight: 700, lineHeight: 1 }}>14</div>
        <div style={{ fontFamily: fontBody, fontSize: 10, color: TEXT_MD, letterSpacing: '0.2em', marginTop: 4 }}>ALERTS</div>
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5, fontFamily: fontMono, fontSize: 10 }}>
        {alerts.map((a, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: TEXT_MD, minWidth: 56 }}>{a.t}</span>
            <span style={{
              padding: '2px 6px', borderRadius: 4,
              background: sevColor[a.sev].bg, color: sevColor[a.sev].fg,
              fontWeight: 700, letterSpacing: '0.08em', minWidth: 32, textAlign: 'center',
            }}>{a.sev}</span>
            <span style={{ color: TEXT_MD, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.label}</span>
          </div>
        ))}
      </div>
    </div>
  </Glass>
);

// ─── code-matrix background ────────────────────────────────────────────
const CodeMatrix = ({ side = 'left' }) => {
  const lines = useMemo(() =>
    Array.from({ length: 60 }).map(() =>
      Math.random().toString(36).slice(2, 2 + Math.floor(Math.random() * 30 + 10)) +
      ' ' + Math.random().toString(36).slice(2, 2 + Math.floor(Math.random() * 14))
    ), []);
  return (
    <div aria-hidden style={{
      position: 'absolute', top: 0, bottom: 0, width: 220,
      [side]: 0,
      pointerEvents: 'none', overflow: 'hidden',
      maskImage: side === 'left'
        ? 'linear-gradient(90deg, rgba(0,0,0,0.55) 0%, transparent 100%)'
        : 'linear-gradient(270deg, rgba(0,0,0,0.55) 0%, transparent 100%)',
      WebkitMaskImage: side === 'left'
        ? 'linear-gradient(90deg, rgba(0,0,0,0.55) 0%, transparent 100%)'
        : 'linear-gradient(270deg, rgba(0,0,0,0.55) 0%, transparent 100%)',
      fontFamily: fontMono, fontSize: 9, color: 'rgba(212,163,115,0.18)',
      lineHeight: '14px', padding: 16, whiteSpace: 'pre',
    }}>
      {lines.join('\n')}
    </div>
  );
};

// ─── top header ────────────────────────────────────────────────────────
const TopHeader = ({
  section, customerName, activeBin, bins, onSwitchBin,
  score, sec, onToggleSec,
}) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '20px 28px', flexWrap: 'wrap', gap: 12,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
      <div style={{ fontFamily: fontDisplay, color: TEXT_HI, fontSize: 22, fontWeight: 600, letterSpacing: '0.04em' }}>
        {section}
      </div>
    </div>

    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <CustomerChip name={customerName} />
      <BinChip active={activeBin} options={bins} onSwitch={onSwitchBin} />

      <button data-testid="period-dropdown" style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 14px', borderRadius: 12,
        background: PANEL, border: `1px solid ${STROKE}`,
        color: TEXT_HI, fontFamily: fontBody, fontSize: 12, cursor: 'pointer',
      }}>
        Last months <ChevronDown size={14} />
      </button>

      {/* Compact security button + popover (replaces big floating card) */}
      <SecurityHeaderButton
        score={score}
        faceid={sec.faceid}
        twofa={sec.twofa}
        session={sec.session}
        onToggle={onToggleSec}
      />

      <button data-testid="header-bell" style={{
        position: 'relative', width: 40, height: 40, borderRadius: 12,
        background: PANEL, border: `1px solid ${STROKE}`, color: TEXT_HI,
        display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
      }}>
        <Bell size={16} />
        <span style={{
          position: 'absolute', top: 8, right: 9, width: 8, height: 8, borderRadius: '50%',
          background: '#ef4444', boxShadow: '0 0 8px #ef4444',
        }} />
      </button>

      <button data-testid="header-profile" style={{
        width: 40, height: 40, borderRadius: '50%',
        background: `linear-gradient(135deg, ${GOLD} 0%, ${GOLD_DK} 100%)`,
        border: `1px solid rgba(247,231,206,0.4)`, cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <User size={18} color={INK} />
      </button>
    </div>
  </div>
);

// ─── main ──────────────────────────────────────────────────────────────
const LuxeDashboardPreview = () => {
  const [active, setActive] = useState('home');
  const [activeBin, setActiveBin] = useState(bins[0]);
  const [sec, setSec] = useState({ faceid: true, twofa: true, session: true });
  const customerName = 'Polaris Built';

  const score = useMemo(() => {
    const base = 60;
    return base + (sec.faceid ? 14 : 0) + (sec.twofa ? 12 : 0) + (sec.session ? 6 : 0);
  }, [sec]);

  return (
    <div data-testid="luxe-dashboard-preview" style={{
      minHeight: '100vh',
      background: `radial-gradient(120% 80% at 50% 0%, #11141a 0%, #07080c 60%, #04050a 100%)`,
      position: 'relative', overflow: 'hidden',
      fontFamily: fontBody, color: TEXT_HI,
    }}>
      <CodeMatrix side="left" />
      <CodeMatrix side="right" />

      <div style={{
        position: 'relative', zIndex: 2,
        maxWidth: 1480, margin: '0 auto', padding: '32px 28px',
      }}>
        <Glass style={{ minHeight: 880 }}>
          <div style={{ display: 'flex', minHeight: 880, height: '100%', position: 'relative' }}>
            {/* Sticky left sidebar — stays in view on scroll */}
            <div style={{
              position: 'sticky', top: 0, alignSelf: 'flex-start',
              minHeight: 880,
              display: 'flex',
              flexShrink: 0,
            }}>
              <Sidebar active={active} onChange={setActive} />
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', minWidth: 0 }}>
              <TopHeader
                section="Home"
                customerName={customerName}
                activeBin={activeBin}
                bins={bins}
                onSwitchBin={setActiveBin}
                score={score}
                sec={sec}
                onToggleSec={(k, v) => setSec((s) => ({ ...s, [k]: v }))}
              />

              {/* Hero stats */}
              <div style={{ padding: '4px 28px 12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
                  <span style={{
                    fontFamily: fontDisplay, color: GOLD_HI, fontSize: 13,
                    letterSpacing: '0.22em', textTransform: 'uppercase',
                  }}>
                    Aurem Pulse
                  </span>
                  <DotMatrix rows={1} cols={20} />
                </div>

                <div style={{
                  fontFamily: fontDisplay, color: GOLD_HI, fontSize: 12,
                  letterSpacing: '0.22em', textTransform: 'uppercase', marginTop: 14,
                }}>
                  Total Revenue
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 24, marginTop: 4 }}>
                  <div style={{ fontFamily: fontDisplay, fontSize: 56, fontWeight: 700, letterSpacing: '-0.02em', color: TEXT_HI }}>
                    292.8k
                  </div>
                  <div style={{ fontFamily: fontMono, color: '#86efac', fontSize: 14 }}>+21.8%</div>
                  <div style={{ fontFamily: fontDisplay, fontSize: 36, fontWeight: 600, color: TEXT_HI }}>+21.8k</div>
                  <div style={{ fontFamily: fontMono, color: '#fca5a5', fontSize: 14 }}>-21.7%</div>
                </div>

                {/* mini equalizer bars (decorative) */}
                <div style={{
                  position: 'absolute', right: 340, top: 150,
                  display: 'flex', alignItems: 'flex-end', gap: 4, height: 70,
                  pointerEvents: 'none',
                }}>
                  {[35, 50, 38, 60, 48, 32, 56, 44].map((h, i) => (
                    <div key={i} style={{
                      width: 12, height: h,
                      borderRadius: 2,
                      background: i % 3 === 0
                        ? `linear-gradient(180deg, ${GOLD_HI}, ${GOLD_DK})`
                        : 'linear-gradient(180deg, #6f7480 0%, #2a2c33 100%)',
                      boxShadow: i % 3 === 0 ? `0 0 10px rgba(212,163,115,0.4)` : 'none',
                    }} />
                  ))}
                </div>

                <div style={{
                  fontFamily: fontDisplay, color: TEXT_HI, fontSize: 14,
                  letterSpacing: '0.05em', marginTop: 28, opacity: 0.8,
                }}>
                  Business Growth <span style={{ color: TEXT_LO, marginLeft: 8 }}>•••••••••••••••••••</span>
                </div>
              </div>

              {/* Hero chart */}
              <div style={{ padding: '0 28px' }}>
                <HeroChart />
              </div>

              {/* Bottom 3 cards */}
              <div style={{
                padding: '20px 28px 28px',
                display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16,
              }}>
                <ActiveUsersCard />
                <RevenueByBinCard />
                <SecurityAlertsCard />
              </div>
            </div>

          </div>
        </Glass>

        {/* AUREM diamond mark — bottom right */}
        <div aria-hidden style={{
          position: 'absolute', bottom: 28, right: 36, zIndex: 5,
          width: 32, height: 32,
          background: `linear-gradient(135deg, ${GOLD_HI}, ${GOLD_DK})`,
          transform: 'rotate(45deg)',
          borderRadius: 6,
          boxShadow: `0 0 20px rgba(212,163,115,0.4)`,
        }}>
          <Sparkles size={14} color={INK} style={{
            position: 'absolute', top: 9, left: 9, transform: 'rotate(-45deg)',
          }} />
        </div>
      </div>
    </div>
  );
};

export default LuxeDashboardPreview;
