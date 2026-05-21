/**
 * PulseCard — wide accent card.
 * Left: $30d revenue + Active/time tags.
 * Right: Website Health · Auto-fix Live · Security Alerts · ORA Repair %.
 *
 * Data: all from `useLuxeDashboardData`.
 *   props.revenue        { value, deltaPct, deltaAbs }
 *   props.websiteHealth  { value, max }
 *   props.autoFix        { value, target }
 *   props.securityAlerts { count }
 *   props.oraRepair      { successPct }
 *   props.active         boolean (pulse heartbeat)
 *   props.lastUpdated    ISO string or null
 */
import React from 'react';

const fmtMoney = (n) => {
  const v = Number(n) || 0;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
};

const Metric = ({ label, value, accent, sub }) => (
  <div data-testid={`pulse-metric-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
       style={{ flex: 1, paddingLeft: 14, borderLeft: '1px solid var(--dash-border)' }}>
    <div style={{ fontSize: 11, color: 'var(--dash-text-faint)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
      {label}
    </div>
    <div style={{ fontSize: 22, fontWeight: 600, color: accent || 'var(--dash-text)', lineHeight: 1.1 }}>
      {value}
    </div>
    {sub && (
      <div style={{ fontSize: 11, color: 'var(--dash-text-faint)', marginTop: 4 }}>{sub}</div>
    )}
  </div>
);

export const PulseCard = ({
  revenue = { value: 0, deltaPct: 0, deltaAbs: 0 },
  websiteHealth = { value: 0, max: 100 },
  autoFix = { value: 0, target: 2000 },
  securityAlerts = { count: 0 },
  oraRepair = { successPct: 0 },
  active = false,
  lastUpdated = null,
}) => {
  const deltaUp = (revenue.deltaPct ?? 0) >= 0;
  return (
    <section data-testid="pulse-card" className="av2-card-accent" style={{ width: '100%' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr', gap: 24, alignItems: 'center' }}
           className="av2-pulse-grid">
        {/* Left — revenue */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span className="av2-pulse-dot" />
            <span style={{ fontSize: 12, color: 'var(--dash-text-muted)', letterSpacing: '0.04em' }}>
              AUREM PULSE
            </span>
            <span className="av2-pill av2-pill-live" data-testid="pulse-active-pill">
              {active ? 'Active' : 'Idle'}
            </span>
          </div>
          <div style={{ fontSize: 38, fontWeight: 700, color: 'var(--dash-text)', lineHeight: 1 }}>
            {fmtMoney(revenue.value)}
          </div>
          <div style={{ marginTop: 8, fontSize: 12, color: 'var(--dash-text-muted)' }}>
            <span style={{ color: deltaUp ? 'var(--dash-green)' : 'var(--dash-red)' }}>
              {deltaUp ? '↑' : '↓'} {Math.abs(revenue.deltaPct ?? 0).toFixed(1)}%
            </span>
            <span style={{ margin: '0 8px', color: 'var(--dash-text-faint)' }}>·</span>
            <span>Total revenue · Last 30 days</span>
            {lastUpdated && (
              <span style={{ marginLeft: 8, color: 'var(--dash-text-faint)' }}>
                · updated {String(lastUpdated).slice(11, 16)}
              </span>
            )}
          </div>
        </div>
        {/* Right — 4 metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <Metric label="Website Health"
                  value={`${websiteHealth.value ?? 0}/${websiteHealth.max ?? 100}`}
                  accent="var(--dash-blue)" />
          <Metric label="Auto-Fix Live"
                  value={`${autoFix.value ?? 0}`}
                  sub={`Target ${autoFix.target ?? 2000}`}
                  accent="var(--dash-green)" />
          <Metric label="Security Alerts"
                  value={`${securityAlerts.count ?? 0}`}
                  accent={(securityAlerts.count ?? 0) > 0 ? 'var(--dash-amber)' : 'var(--dash-text)'} />
          <Metric label="ORA Repair"
                  value={`${oraRepair.successPct ?? 0}%`}
                  accent="var(--dash-purple)" />
        </div>
      </div>
    </section>
  );
};

export default PulseCard;
