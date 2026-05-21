/**
 * AgentBars — Active Agents card with 5 fixed slots
 * (Scout/Architect/Envoy/Closer/Orchestra). Falls back to first 5
 * agents from the live array. Bar height = activity_score (0..100).
 */
import React, { useMemo } from 'react';

const SLOTS = ['Scout', 'Architect', 'Envoy', 'Closer', 'Orchestra'];

const Bar = ({ name, value, count }) => {
  const h = Math.max(6, Math.min(100, value));
  const hot = value >= 60;
  return (
    <div data-testid={`agent-bar-${name.toLowerCase()}`}
         style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 10, color: 'var(--dash-text-faint)', fontVariantNumeric: 'tabular-nums' }}>
        {count >= 1000 ? `${(count / 1000).toFixed(1)}k` : count}
      </div>
      <div style={{
        position: 'relative', width: '100%', maxWidth: 28, height: 88,
        background: 'var(--dash-track)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div className="av2-bar" style={{
          position: 'absolute', bottom: 0, left: 0, right: 0,
          height: `${h}%`,
          background: hot
            ? 'linear-gradient(180deg, var(--dash-orange) 0%, var(--dash-gold-bright) 100%)'
            : 'linear-gradient(180deg, rgba(255,107,0,0.45) 0%, rgba(201,168,76,0.30) 100%)',
        }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--dash-text-muted)', letterSpacing: '0.04em' }}>
        {name.slice(0, 6)}
      </div>
    </div>
  );
};

export const AgentBars = ({ agents = [], running = 0, uptime = '99.9%' }) => {
  // Map provided agents to the 5 slots — by name when possible, else fill order.
  const rows = useMemo(() => {
    const byKey = new Map(
      (agents || []).map((a) => [String(a.k || '').toLowerCase(), a]),
    );
    return SLOTS.map((slot) => {
      const a = byKey.get(slot.toLowerCase())
        || (agents && agents[SLOTS.indexOf(slot)])
        || { v: 0, n: 0 };
      return { name: slot, value: Number(a.v) || 0, count: Number(a.n) || 0 };
    });
  }, [agents]);

  return (
    <section data-testid="agents-card" className="av2-card" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>
          Active Agents
        </h3>
        <span className="av2-pill av2-pill-live">{running} running</span>
      </header>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, paddingTop: 4 }}>
        {rows.map((r) => <Bar key={r.name} {...r} />)}
      </div>
      <footer style={{ display: 'flex', justifyContent: 'space-between',
                       fontSize: 11, color: 'var(--dash-text-muted)',
                       paddingTop: 8, borderTop: '1px solid var(--dash-divider)' }}>
        <span>Uptime <strong style={{ color: 'var(--dash-text)' }}>{uptime}</strong></span>
        <span>Real-time</span>
      </footer>
    </section>
  );
};

export default AgentBars;
