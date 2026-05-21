/**
 * MetricRow — the 4-column metric row (Leads/Outreach/Responses/Meetings).
 * Each tile: label + colored number + thin progress bar + subtitle.
 */
import React from 'react';

const TILES = [
  { k: 'leads_found',    label: 'Leads Found',    color: 'var(--dash-blue)',   sub: 'Last 30 days' },
  { k: 'outreach_sent',  label: 'Outreach Sent',  color: 'var(--dash-purple)', sub: 'Email + SMS + Voice' },
  { k: 'responses',      label: 'Responses',      color: 'var(--dash-amber)',  sub: 'All channels' },
  { k: 'meetings_booked',label: 'Meetings Booked',color: 'var(--dash-green)',  sub: 'Confirmed only' },
];

export const MetricRow = ({ data = {} }) => {
  const values = TILES.map((t) => Number(data[t.k]) || 0);
  const max = Math.max(1, ...values);
  return (
    <div className="av2-grid-4">
      {TILES.map((t, i) => {
        const v = values[i];
        const pct = Math.round((v / max) * 100);
        return (
          <div key={t.k} data-testid={`metric-${t.k}`} className="av2-card"
               style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--dash-text-muted)', textTransform: 'uppercase',
                          letterSpacing: '0.06em' }}>
              {t.label}
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color: t.color, lineHeight: 1 }}>
              {v.toLocaleString()}
            </div>
            <div style={{ height: 3, background: 'var(--dash-track)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${Math.max(4, pct)}%`, height: '100%', background: t.color,
                            transition: 'width 400ms ease' }} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>{t.sub}</div>
          </div>
        );
      })}
    </div>
  );
};

export default MetricRow;
