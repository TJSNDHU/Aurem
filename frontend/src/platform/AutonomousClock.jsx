/**
 * AutonomousClock — AUREM signature symbol (iter 308)
 *
 * "A system that fixes itself while the owner sleeps."
 *
 * Circular self-repair arrow with a gold core.
 * - Survives without color (works in monochrome).
 * - Drawable from memory (single circular arrow + dot).
 * - Subtle 24s rotation animation when `animated` prop is true.
 * - data-testid="autonomous-clock-{size}"
 */
import React from 'react';

const GOLD = '#C9A227';
const INK = '#0A0A0B';
const PAPER = '#F2EDE4';

export default function AutonomousClock({
  size = 64,
  variant = 'gold',          // 'gold' | 'paper' | 'ink' | 'mono'
  animated = false,
  strokeWidth = 4,
  className,
  style,
}) {
  const colors = {
    gold:  { ring: GOLD,  core: GOLD,  glow: 'rgba(201,162,39,0.35)' },
    paper: { ring: PAPER, core: GOLD,  glow: 'rgba(242,237,228,0.25)' },
    ink:   { ring: INK,   core: GOLD,  glow: 'rgba(10,10,11,0.4)' },
    mono:  { ring: 'currentColor', core: 'currentColor', glow: 'transparent' },
  }[variant] || { ring: GOLD, core: GOLD, glow: 'rgba(201,162,39,0.35)' };

  const id = React.useId();
  const animClass = animated ? `aurem-clock-spin-${id.replace(/:/g, '')}` : '';

  return (
    <span
      role="img"
      aria-label="AUREM Autonomous Clock"
      data-testid={`autonomous-clock-${size}`}
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        lineHeight: 0,
        filter: animated ? `drop-shadow(0 0 ${size / 6}px ${colors.glow})` : 'none',
        ...style,
      }}
    >
      {animated && (
        <style>{`
          @keyframes ${animClass} {
            from { transform: rotate(0deg); }
            to   { transform: rotate(360deg); }
          }
          .${animClass} { animation: ${animClass} 24s linear infinite;
            transform-origin: 50% 50%; transform-box: fill-box; }
        `}</style>
      )}
      <svg
        width={size} height={size} viewBox="0 0 64 64"
        xmlns="http://www.w3.org/2000/svg" fill="none"
      >
        <g className={animClass || undefined}>
          {/* Self-repair arc — open at the top with arrowhead */}
          <path
            d="M32 6 a26 26 0 1 0 18.4 7.6"
            stroke={colors.ring}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            fill="none"
          />
          {/* Arrowhead */}
          <path
            d="M50.4 13.6 L46.2 6.5 L54 6.0 Z"
            fill={colors.ring}
          />
        </g>
        {/* Gold core (aurum) — fixed center, always visible */}
        <circle cx="32" cy="32" r="6" fill={colors.core} />
        <circle
          cx="32" cy="32" r="2.4"
          fill={variant === 'mono' ? 'currentColor' : INK}
        />
      </svg>
    </span>
  );
}
