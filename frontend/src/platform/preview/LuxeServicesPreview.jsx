/**
 * LuxeServicesPreview — services-oriented variant.
 * Route: /preview/luxe-services
 *
 * Frame-to-frame match of "Pixel Heartbeat: ACTIVE" reference:
 *   - Charcoal canvas
 *   - Tall gold-rimmed left sidebar with big icon panels
 *     (Home / Live Health / Automation / Security / CRM / Subscription / Settings)
 *   - Top "PIXEL HEARTBEAT: ACTIVE" bar with animated green ECG pulse
 *   - Center: 98% HEALTH circular gauge with gold particle dust
 *   - Bottom-left: Live Security Feed mini card
 *   - Bottom-right: Automation Logs mini card
 *
 * Existing /preview/luxe-dashboard remains untouched.
 */

import React, { useMemo, useState } from 'react';
import {
  Rocket, Search, Bot, Shield, Users, CreditCard, Settings as Cog,
  Activity,
} from 'lucide-react';

// ─── tokens ────────────────────────────────────────────────────────────
const GOLD = '#D4A373';
const GOLD_HI = '#F7E7CE';
const GOLD_DK = '#8B6F44';
const ORANGE = '#FF8A3D';
const INK = '#0A0A0F';
const PANEL = 'rgba(22,24,28,0.55)';
const STROKE = 'rgba(212,163,115,0.20)';
const TEXT_HI = '#E8E4DE';
const TEXT_MD = '#9A9590';
const TEXT_LO = '#6A6560';

const fontDisplay = "'Cinzel', 'Montserrat', serif";
const fontBody = "'Jost', 'Inter', system-ui, sans-serif";
const fontMono = "'JetBrains Mono', ui-monospace, monospace";

// ─── nav items (fixed order from reference) ────────────────────────────
const NAV = [
  { k: 'home',         label: 'Home',         icon: Rocket     },
  { k: 'live-health',  label: 'Live Health',  icon: Search     },
  { k: 'automation',   label: 'Automation',   icon: Bot        },
  { k: 'security',     label: 'Security',     icon: Shield     },
  { k: 'crm',          label: 'CRM',          icon: Users      },
  { k: 'subscription', label: 'Subscription', icon: CreditCard },
  { k: 'settings',     label: 'Settings',     icon: Cog        },
];

// ─── primitives ────────────────────────────────────────────────────────
const Glass = ({ children, style, ...rest }) => (
  <div
    style={{
      background: `linear-gradient(155deg, ${PANEL} 0%, rgba(14,16,20,0.55) 55%, rgba(36,38,44,0.45) 100%)`,
      border: `1px solid ${STROKE}`,
      borderRadius: 22,
      backdropFilter: 'blur(22px) saturate(160%)',
      WebkitBackdropFilter: 'blur(22px) saturate(160%)',
      boxShadow: '0 30px 80px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)',
      position: 'relative',
      overflow: 'hidden',
      ...style,
    }}
    {...rest}
  >
    {children}
  </div>
);

// ─── Sidebar — tall gold-rimmed panel, big icon tiles ──────────────────
const Sidebar = ({ active, onChange }) => (
  <Glass
    style={{
      width: 280, flexShrink: 0,
      padding: 20,
      display: 'flex', flexDirection: 'column', gap: 12,
      border: `1px solid rgba(212,163,115,0.45)`,
      boxShadow:
        '0 30px 80px rgba(0,0,0,0.55), inset 0 0 0 1px rgba(212,163,115,0.18), 0 0 0 1px rgba(212,163,115,0.12)',
    }}
  >
    {/* header */}
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 8px', marginBottom: 8,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        background: `linear-gradient(135deg, ${GOLD_HI} 0%, ${GOLD} 50%, ${GOLD_DK} 100%)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: fontDisplay, fontWeight: 800, fontSize: 22, color: INK,
        boxShadow: `0 0 20px rgba(212,163,115,0.45), inset 0 1px 0 rgba(255,255,255,0.4)`,
      }}>
        A
      </div>
      <div>
        <div style={{
          fontFamily: fontDisplay, color: GOLD_HI, fontSize: 14, fontWeight: 700,
          letterSpacing: '0.16em',
        }}>
          AUREM BUSINESS ORA
        </div>
        <div style={{
          fontFamily: fontBody, color: TEXT_MD, fontSize: 10,
          letterSpacing: '0.08em', marginTop: 2,
        }}>
          Services-oriented dashboard
        </div>
      </div>
    </div>

    {/* nav tiles */}
    {NAV.map(({ k, label, icon: Icon }) => {
      const on = active === k;
      return (
        <button
          key={k}
          data-testid={`sv-nav-${k}`}
          onClick={() => onChange(k)}
          style={{
            display: 'flex', alignItems: 'center', gap: 16,
            padding: '14px 18px',
            borderRadius: 14,
            background: on
              ? 'linear-gradient(135deg, rgba(255,138,61,0.10) 0%, rgba(255,138,61,0.04) 100%)'
              : 'rgba(20,22,26,0.55)',
            border: on ? `1.5px solid ${ORANGE}` : `1px solid ${STROKE}`,
            color: on ? GOLD_HI : TEXT_HI,
            fontFamily: fontDisplay, fontSize: 16,
            letterSpacing: '0.04em',
            cursor: 'pointer',
            position: 'relative',
            transition: 'all .25s ease',
            boxShadow: on
              ? `0 0 24px rgba(255,138,61,0.30), inset 0 0 18px rgba(255,138,61,0.08)`
              : 'inset 0 1px 0 rgba(255,255,255,0.02)',
          }}
        >
          <Icon
            size={26}
            strokeWidth={1.6}
            color={on ? GOLD_HI : GOLD}
            style={{ filter: `drop-shadow(0 0 6px ${on ? 'rgba(255,138,61,0.55)' : 'rgba(212,163,115,0.35)'})` }}
          />
          <span>{label}</span>
        </button>
      );
    })}
  </Glass>
);

// ─── Pixel Heartbeat top bar with animated ECG ─────────────────────────
const HeartbeatBar = ({ active = true }) => (
  <Glass style={{ padding: '20px 28px' }}>
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18,
    }}>
      <span style={{
        fontFamily: fontDisplay, fontSize: 22, fontWeight: 700,
        letterSpacing: '0.14em', color: TEXT_HI,
      }}>
        PIXEL HEARTBEAT:
      </span>
      <span
        data-testid="heartbeat-state"
        style={{
          fontFamily: fontDisplay, fontSize: 22, fontWeight: 800,
          letterSpacing: '0.18em',
          color: active ? '#22c55e' : '#ef4444',
          textShadow: active ? '0 0 18px rgba(34,197,94,0.6)' : '0 0 18px rgba(239,68,68,0.6)',
        }}
      >
        {active ? 'ACTIVE' : 'OFFLINE'}
      </span>
      {/* animated ECG */}
      <ECGPulse on={active} />
    </div>
    {/* glow rail underneath */}
    <div aria-hidden style={{
      position: 'absolute', left: '15%', right: '15%', bottom: 8, height: 2,
      background: active
        ? 'linear-gradient(90deg, transparent, rgba(34,197,94,0.6), transparent)'
        : 'linear-gradient(90deg, transparent, rgba(239,68,68,0.5), transparent)',
      filter: 'blur(1px)',
      animation: 'svPulseRail 2.4s ease-in-out infinite',
    }} />
    <style>{`
      @keyframes svPulseRail {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
      }
      @keyframes svEcgScroll {
        from { transform: translateX(0); }
        to { transform: translateX(-260px); }
      }
      @keyframes svGaugeSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
      @keyframes svDustFlicker {
        0%, 100% { opacity: 0.85; }
        50% { opacity: 1; }
      }
    `}</style>
  </Glass>
);

const ECGPulse = ({ on }) => (
  <div style={{
    width: 130, height: 36, position: 'relative', overflow: 'hidden',
    display: 'flex', alignItems: 'center',
  }}>
    <svg
      width="520" height="36" viewBox="0 0 520 36"
      style={{
        animation: on ? 'svEcgScroll 1.4s linear infinite' : 'none',
      }}
    >
      <defs>
        <linearGradient id="ecgStroke" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="rgba(34,197,94,0.0)" />
          <stop offset="20%" stopColor="rgba(34,197,94,0.6)" />
          <stop offset="80%" stopColor="rgba(34,197,94,0.95)" />
          <stop offset="100%" stopColor="rgba(34,197,94,0.5)" />
        </linearGradient>
      </defs>
      {[0, 1].map((cycle) => {
        const x0 = cycle * 260;
        const path = [
          `M ${x0} 18`,
          `L ${x0 + 60} 18`,
          `L ${x0 + 70} 6`,
          `L ${x0 + 80} 30`,
          `L ${x0 + 90} 18`,
          `L ${x0 + 110} 18`,
          `L ${x0 + 120} 12`,
          `L ${x0 + 130} 24`,
          `L ${x0 + 140} 18`,
          `L ${x0 + 260} 18`,
        ].join(' ');
        return (
          <path
            key={cycle}
            d={path}
            fill="none"
            stroke="url(#ecgStroke)"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ filter: 'drop-shadow(0 0 6px rgba(34,197,94,0.7))' }}
          />
        );
      })}
    </svg>
    <Activity
      size={20}
      color="#22c55e"
      style={{
        position: 'absolute', right: -22, top: 8,
        filter: 'drop-shadow(0 0 6px rgba(34,197,94,0.7))',
      }}
    />
  </div>
);

// ─── Health Gauge ──────────────────────────────────────────────────────
const HealthGauge = ({ value = 98 }) => {
  // particle dust ring (deterministic so SSR-friendly)
  const dust = useMemo(() => {
    const arr = [];
    const seed = (n) => Math.sin(n * 12.9898) * 43758.5453 % 1;
    for (let i = 0; i < 280; i += 1) {
      const angle = i * (Math.PI * 2 / 280);
      const radial = 0.78 + Math.abs(seed(i + 7)) * 0.32; // 0.78..1.10
      const size = 0.6 + Math.abs(seed(i + 17)) * 1.6;
      const lightness = 0.5 + Math.abs(seed(i + 23)) * 0.5;
      arr.push({ angle, radial, size, lightness });
    }
    return arr;
  }, []);

  const ticks = useMemo(() => {
    const arr = [];
    const startA = Math.PI * 0.85;   // ~153deg
    const sweep  = Math.PI * 1.30;   // ~234deg
    for (let i = 0; i <= 100; i += 1) {
      const t = i / 100;
      const a = startA + sweep * t;
      const major = i % 10 === 0;
      arr.push({ a, major, value: i });
    }
    return arr;
  }, []);

  const size = 540;
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = 230;
  const rInner = 175;

  return (
    <div style={{ position: 'relative', width: size, height: size, margin: '0 auto' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <radialGradient id="svGaugeBg" cx="50%" cy="50%" r="55%">
            <stop offset="0%"  stopColor="rgba(20,22,26,0.0)" />
            <stop offset="60%" stopColor="rgba(20,22,26,0.0)" />
            <stop offset="100%" stopColor="rgba(8,9,12,0.55)" />
          </radialGradient>
          <linearGradient id="svGaugeRim" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor={GOLD_HI} />
            <stop offset="50%" stopColor={GOLD} />
            <stop offset="100%" stopColor={GOLD_DK} />
          </linearGradient>
          <radialGradient id="svDustGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={GOLD_HI} stopOpacity={1} />
            <stop offset="100%" stopColor={GOLD_DK} stopOpacity={0} />
          </radialGradient>
        </defs>

        {/* dim background dome */}
        <circle cx={cx} cy={cy} r={rOuter + 6} fill="url(#svGaugeBg)" />

        {/* outer rim arc (open at bottom) */}
        <path
          d={describeArc(cx, cy, rOuter + 8, 153, 387)}
          fill="none"
          stroke="url(#svGaugeRim)"
          strokeWidth={1.5}
          strokeLinecap="round"
          opacity={0.6}
        />
        <path
          d={describeArc(cx, cy, rOuter, 153, 387)}
          fill="none"
          stroke="url(#svGaugeRim)"
          strokeWidth={2.5}
          strokeLinecap="round"
        />

        {/* inner glass dome arc */}
        <path
          d={describeArc(cx, cy, rInner + 30, 153, 387)}
          fill="none"
          stroke="rgba(212,163,115,0.18)"
          strokeWidth={48}
          strokeLinecap="butt"
          style={{ filter: 'blur(1px)' }}
        />

        {/* tick marks */}
        {ticks.map((t, i) => {
          const r1 = rOuter - 12;
          const r2 = t.major ? rOuter - 30 : rOuter - 22;
          const x1 = cx + Math.cos(t.a) * r1;
          const y1 = cy + Math.sin(t.a) * r1;
          const x2 = cx + Math.cos(t.a) * r2;
          const y2 = cy + Math.sin(t.a) * r2;
          return (
            <line
              key={i}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={t.major ? GOLD_HI : GOLD}
              strokeWidth={t.major ? 1.6 : 0.8}
              opacity={t.major ? 0.9 : 0.5}
            />
          );
        })}

        {/* tick labels (10/20/.../90) */}
        {ticks.filter((t) => t.major && t.value > 0 && t.value < 100).map((t, i) => {
          const r = rOuter - 50;
          const x = cx + Math.cos(t.a) * r;
          const y = cy + Math.sin(t.a) * r;
          return (
            <text
              key={i}
              x={x} y={y}
              textAnchor="middle" dominantBaseline="middle"
              fill={TEXT_MD}
              fontFamily={fontBody}
              fontSize={13}
              opacity={0.85}
            >
              {t.value}%
            </text>
          );
        })}
        {/* 0 + 100 labels */}
        <text x={cx + Math.cos(Math.PI * 0.85) * (rOuter - 50)}
              y={cy + Math.sin(Math.PI * 0.85) * (rOuter - 50) + 18}
              textAnchor="middle" fill={TEXT_MD} fontFamily={fontBody} fontSize={12}>
          0
        </text>
        <text x={cx + Math.cos(Math.PI * 0.85 + Math.PI * 1.3) * (rOuter - 50)}
              y={cy + Math.sin(Math.PI * 0.85 + Math.PI * 1.3) * (rOuter - 50) + 18}
              textAnchor="middle" fill={TEXT_MD} fontFamily={fontBody} fontSize={12}>
          100%
        </text>

        {/* Particle dust ring (animated) */}
        <g style={{ animation: 'svDustFlicker 3s ease-in-out infinite' }}>
          {dust.map((d, i) => {
            const r = (rInner + (rOuter - rInner) * d.radial * 0.95);
            const x = cx + Math.cos(d.angle) * r;
            const y = cy + Math.sin(d.angle) * r;
            return (
              <circle
                key={i}
                cx={x} cy={y} r={d.size}
                fill={GOLD_HI}
                opacity={d.lightness * 0.85}
                style={{ filter: 'drop-shadow(0 0 4px rgba(247,231,206,0.6))' }}
              />
            );
          })}
        </g>

        {/* progress arc to 98% */}
        <path
          d={describeArc(cx, cy, rOuter - 4, 153, 153 + 234 * (value / 100))}
          fill="none"
          stroke="url(#svGaugeRim)"
          strokeWidth={4}
          strokeLinecap="round"
          style={{ filter: 'drop-shadow(0 0 10px rgba(247,231,206,0.6))' }}
        />
      </svg>

      {/* center label */}
      <div style={{
        position: 'absolute', inset: 0,
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{
          fontFamily: fontDisplay, color: '#FFFFFF', fontSize: 132,
          fontWeight: 700, letterSpacing: '-0.04em', lineHeight: 1,
          textShadow: '0 4px 30px rgba(247,231,206,0.18)',
        }}>
          {value}%
        </div>
        <div style={{
          fontFamily: fontDisplay, color: GOLD_HI, fontSize: 22,
          letterSpacing: '0.32em', marginTop: 6, fontWeight: 600,
        }}>
          HEALTH
        </div>
      </div>

      {/* faint code annotations (decorative, like reference) */}
      <CodeAnnotations />
    </div>
  );
};

// helper: SVG arc
function polar(cx, cy, r, deg) {
  const rad = (deg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}
function describeArc(cx, cy, r, startAngle, endAngle) {
  const start = polar(cx, cy, r, endAngle);
  const end = polar(cx, cy, r, startAngle);
  const large = endAngle - startAngle <= 180 ? '0' : '1';
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 0 ${end.x} ${end.y}`;
}

// faint annotations around the gauge (decorative)
const CodeAnnotations = () => (
  <>
    <div style={{
      position: 'absolute', top: 60, left: 30, width: 160,
      fontFamily: fontMono, fontSize: 8, lineHeight: '11px',
      color: 'rgba(212,163,115,0.30)', whiteSpace: 'pre',
    }}>
      {`processing.scan
> tenant=AURE-8829
> heartbeat=ACTIVE
> latency=42ms
> repair_pipeline=on`}
    </div>
    <div style={{
      position: 'absolute', top: 60, right: 30, width: 160,
      fontFamily: fontMono, fontSize: 8, lineHeight: '11px',
      color: 'rgba(212,163,115,0.30)', whiteSpace: 'pre',
      textAlign: 'right',
    }}>
      {`agents.live
> scout=ok
> hunter=ok
> closer=ok
> envoy=ok`}
    </div>
  </>
);

// ─── bottom mini cards ─────────────────────────────────────────────────
const FeedCard = ({ title, items, dot }) => (
  <Glass style={{ padding: 16, width: 280 }}>
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 10,
    }}>
      <div style={{
        fontFamily: fontDisplay, color: TEXT_HI, fontSize: 13,
        letterSpacing: '0.04em', fontWeight: 600,
      }}>
        {title}
      </div>
      <Activity size={14} color={GOLD} />
    </div>
    <div style={{
      height: 1, background: `linear-gradient(90deg, transparent, ${GOLD}, transparent)`,
      opacity: 0.4, marginBottom: 8,
    }} />
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {items.map((it, i) => (
        <div key={i} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          fontFamily: fontBody, fontSize: 12, color: TEXT_HI,
        }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: it.dot ?? dot,
              boxShadow: `0 0 6px ${it.dot ?? dot}`,
            }} />
            {it.label}
          </span>
          <span style={{ fontFamily: fontMono, color: TEXT_MD }}>{it.value}</span>
        </div>
      ))}
    </div>
  </Glass>
);

// ─── main ──────────────────────────────────────────────────────────────
const LuxeServicesPreview = () => {
  const [active, setActive] = useState('home');

  const securityFeed = [
    { label: 'Live Security Feed', value: 209, dot: '#22c55e' },
    { label: 'Live Security Feed', value: 300, dot: '#22c55e' },
    { label: 'Live Security Feed', value: 309, dot: '#22c55e' },
    { label: 'Live Security Feed', value: 326, dot: '#ef4444' },
  ];
  const automationLogs = [
    { label: 'Automation Logs', value: 1094 },
    { label: 'Automation Logs', value: 1259 },
    { label: 'Automation Logs', value: 2000 },
    { label: 'Automation Logs', value: 1298 },
  ];

  return (
    <div data-testid="luxe-services-preview" style={{
      minHeight: '100vh',
      background: `radial-gradient(120% 80% at 50% 0%, #1a1d22 0%, #0e1014 60%, #07080c 100%)`,
      position: 'relative', overflow: 'hidden',
      fontFamily: fontBody, color: TEXT_HI,
    }}>
      <div style={{
        maxWidth: 1480, margin: '0 auto', padding: '32px 28px',
        display: 'flex', gap: 24,
      }}>
        {/* Left sidebar */}
        <Sidebar active={active} onChange={setActive} />

        {/* Right column: heartbeat bar + main content card */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}>
          <HeartbeatBar active />

          <Glass style={{ padding: 32, position: 'relative', minHeight: 760 }}>
            {/* Header label */}
            <div style={{
              fontFamily: fontDisplay, color: TEXT_HI, fontSize: 22,
              fontWeight: 700, letterSpacing: '0.02em',
            }}>
              Health Score
            </div>
            <div style={{
              fontFamily: fontBody, fontSize: 11, color: TEXT_LO,
              marginTop: 6, maxWidth: 340, lineHeight: 1.5,
            }}>
              Real-time tenant health composed of pixel heartbeat, agent uptime,
              auto-repair success rate, and outreach deliverability.
            </div>

            {/* Center gauge */}
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center' }}>
              <HealthGauge value={98} />
            </div>

            {/* Bottom feeds */}
            <div style={{
              position: 'absolute', left: 28, right: 28, bottom: 24,
              display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end',
              pointerEvents: 'none',
            }}>
              <div style={{ pointerEvents: 'auto' }}>
                <FeedCard title="Live Security Feed" items={securityFeed} dot="#22c55e" />
              </div>
              <div style={{ pointerEvents: 'auto' }}>
                <FeedCard title="Automation Logs" items={automationLogs} dot={GOLD} />
              </div>
            </div>

            {/* AUREM diamond mark */}
            <div aria-hidden style={{
              position: 'absolute', bottom: 18, right: 22,
              width: 26, height: 26,
              background: `linear-gradient(135deg, ${GOLD_HI}, ${GOLD_DK})`,
              transform: 'rotate(45deg)',
              borderRadius: 5,
              boxShadow: `0 0 16px rgba(212,163,115,0.45)`,
            }} />
          </Glass>
        </div>
      </div>
    </div>
  );
};

export default LuxeServicesPreview;
