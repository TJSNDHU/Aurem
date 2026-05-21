/**
 * VanguardRing — circular score ring + status pill list.
 * Ring uses conic-gradient; status row shows site/platform/backlinks.
 */
import React from 'react';

const ringColorFor = (score) => {
  if (score >= 85) return 'var(--dash-green)';
  if (score >= 60) return 'var(--dash-blue)';
  if (score >= 40) return 'var(--dash-amber)';
  return 'var(--dash-red)';
};

const StatusRow = ({ label, value, ok = true }) => (
  <div data-testid={`vg-row-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
       style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '6px 0', borderBottom: '1px solid var(--dash-divider)' }}>
    <span style={{ fontSize: 12, color: 'var(--dash-text-muted)' }}>{label}</span>
    <span style={{ fontSize: 12, color: ok ? 'var(--dash-green)' : 'var(--dash-amber)', fontWeight: 500 }}>
      {value}
    </span>
  </div>
);

export const VanguardRing = ({
  score = 0,
  siteShield = 0,
  platform = 0,
  backlinks = 0,
  rateLimiter = 'memory',
  rlsEnforced = false,
}) => {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const deg = (clamped / 100) * 360;
  const color = ringColorFor(clamped);
  return (
    <section data-testid="vanguard-card" className="av2-card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>
          Vanguard Security
        </h3>
        <span style={{ fontSize: 10, color: 'var(--dash-text-faint)', letterSpacing: '0.06em' }}>
          {rateLimiter === 'redis' ? 'REDIS' : 'MEMORY'} · {rlsEnforced ? 'RLS✓' : 'RLS✗'}
        </span>
      </header>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div data-testid="vg-ring" style={{
          width: 92, height: 92, borderRadius: '50%',
          background: `conic-gradient(${color} 0deg ${deg}deg, var(--dash-track) ${deg}deg 360deg)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <div style={{
            width: 72, height: 72, borderRadius: '50%', background: 'var(--dash-card)',
            border: '1px solid var(--dash-border)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--dash-text)' }}>{clamped}</div>
            <div style={{ fontSize: 9, color: 'var(--dash-text-faint)', letterSpacing: '0.08em' }}>SCORE</div>
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <StatusRow label="Site Shield" value={`${siteShield}/100`} ok={siteShield >= 60} />
          <StatusRow label="Platform" value={`${platform}/100`} ok={platform >= 60} />
          <StatusRow label="Backlinks" value={`${backlinks}/100`} ok={backlinks >= 60} />
        </div>
      </div>
    </section>
  );
};

export default VanguardRing;
