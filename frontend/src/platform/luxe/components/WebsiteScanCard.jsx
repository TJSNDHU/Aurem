/**
 * WebsiteScanCard — 4 rows: GEO / SEC / ACC / SEO.
 * Each row: label + sub + colored score badge.
 */
import React from 'react';

const ROWS = [
  { k: 'geo', label: 'GEO',  sub: 'Geographic reach · top-5 markets',  color: 'var(--dash-blue)' },
  { k: 'sec', label: 'SEC',  sub: 'TLS · CSP · HSTS · headers',        color: 'var(--dash-amber)' },
  { k: 'acc', label: 'ACC',  sub: 'WCAG · ARIA · keyboard',            color: 'var(--dash-green)' },
  { k: 'seo', label: 'SEO',  sub: 'Performance · LCP · metadata',      color: 'var(--dash-purple)' },
];

const badge = (v) => {
  const n = Math.max(0, Math.min(100, Number(v) || 0));
  let bg;
  if (n >= 80) bg = 'rgba(52,199,89,0.16)';
  else if (n >= 50) bg = 'rgba(255,159,10,0.16)';
  else bg = 'rgba(255,69,58,0.16)';
  return bg;
};

export const WebsiteScanCard = ({ scan = {}, lastScan = '—' }) => (
  <section data-testid="website-scan-card" className="av2-card"
           style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
    <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>Website Scan</h3>
      <span style={{ fontSize: 11, color: 'var(--dash-text-faint)' }}>Last: {String(lastScan).slice(0, 10)}</span>
    </header>
    {ROWS.map((r) => {
      const v = Number(scan[r.k]) || 0;
      return (
        <div key={r.k} data-testid={`scan-row-${r.k}`}
             style={{ display: 'flex', alignItems: 'center', gap: 12,
                      padding: '10px 0', borderTop: '1px solid var(--dash-divider)' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--dash-text)', letterSpacing: '0.04em' }}>{r.label}</div>
            <div style={{ fontSize: 11, color: 'var(--dash-text-muted)' }}>{r.sub}</div>
          </div>
          <span style={{
            padding: '6px 10px', borderRadius: 8,
            background: badge(v), color: r.color, fontSize: 13, fontWeight: 600,
            minWidth: 48, textAlign: 'center', fontVariantNumeric: 'tabular-nums',
          }}>
            {v}
          </span>
        </div>
      );
    })}
  </section>
);

export default WebsiteScanCard;
