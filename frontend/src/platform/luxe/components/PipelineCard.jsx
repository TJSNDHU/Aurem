/**
 * PipelineCard — 5 stages with dot + label + count.
 * Stages: Discovered/Contacted/Responded/Interested/Closed.
 *
 * Accepts:
 *   props.stages: [{ stage, count }]   (from /api/customer/results-pipeline)
 *   props.total:   number
 */
import React from 'react';

const ORDER = ['Discovered', 'Contacted', 'Responded', 'Interested', 'Closed'];
const DOT_COLOR = {
  Discovered: 'var(--dash-text-muted)',
  Contacted:  'var(--dash-blue)',
  Responded:  'var(--dash-purple)',
  Interested: 'var(--dash-amber)',
  Closed:     'var(--dash-green)',
};

export const PipelineCard = ({ stages = [], total = 0 }) => {
  const byName = new Map((stages || []).map((s) => [String(s.stage), Number(s.count) || 0]));
  const rows = ORDER.map((name) => ({
    name,
    count: byName.get(name) ?? byName.get(name.toUpperCase()) ?? byName.get(name.toLowerCase()) ?? 0,
  }));
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <section data-testid="pipeline-card" className="av2-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>
          Pipeline This Month
        </h3>
        <span style={{ fontSize: 11, color: 'var(--dash-text-muted)' }}>Total: <strong style={{ color: 'var(--dash-text)' }}>{total}</strong></span>
      </header>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map((r) => {
          const pct = Math.round((r.count / max) * 100);
          const color = DOT_COLOR[r.name];
          return (
            <div key={r.name} data-testid={`pipeline-${r.name.toLowerCase()}`}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            marginBottom: 4, fontSize: 12 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--dash-text-muted)' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block' }} />
                  {r.name}
                </span>
                <span style={{ color: 'var(--dash-text)', fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                  {r.count}
                </span>
              </div>
              <div style={{ height: 4, background: 'var(--dash-track)', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{
                  width: `${pct}%`, height: '100%', background: color,
                  transition: 'width 400ms ease',
                }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default PipelineCard;
