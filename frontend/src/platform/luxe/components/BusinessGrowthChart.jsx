/**
 * BusinessGrowthChart — grouped bar chart, Sep → May.
 * Three series: Revenue / Leads / Auto-fixes. Pure SVG, no recharts dep.
 *
 * Accepts:
 *   props.series: [{ m: 'Sep', revenue, leads, fixes }, ...]
 */
import React, { useMemo } from 'react';

const COLORS = { revenue: 'var(--dash-purple)', leads: 'var(--dash-blue)', fixes: 'var(--dash-green)' };

const FALLBACK_MONTHS = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'];

export const BusinessGrowthChart = ({ series = [] }) => {
  // Normalize / pad to 9 buckets so empty state still draws a calm axis.
  const rows = useMemo(() => {
    if (!series || series.length === 0) {
      return FALLBACK_MONTHS.map((m) => ({ m, revenue: 0, leads: 0, fixes: 0 }));
    }
    return series.slice(-9).map((d) => ({
      m: String(d.m || '').slice(0, 3),
      revenue: Number(d.revenue ?? d.a ?? 0),
      leads:   Number(d.leads   ?? d.b ?? 0),
      fixes:   Number(d.fixes   ?? d.c ?? 0),
    }));
  }, [series]);

  const max = Math.max(
    1,
    ...rows.flatMap((r) => [r.revenue, r.leads, r.fixes]),
  );
  const width = 100, height = 60;            // viewBox units, percent-based bars
  const groupW = width / rows.length;
  const barW = groupW / 4;                   // 3 bars + 1 gap

  return (
    <section data-testid="growth-card" className="av2-card"
             style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--dash-text)' }}>
          Business Growth
        </h3>
        <div style={{ display: 'flex', gap: 14, fontSize: 11, color: 'var(--dash-text-muted)' }}>
          {[['Revenue','revenue'], ['Leads','leads'], ['Auto-fixes','fixes']].map(([l, k]) => (
            <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: COLORS[k], display: 'inline-block' }} />
              {l}
            </span>
          ))}
        </div>
      </header>
      <div style={{ width: '100%', height: 220, position: 'relative' }} data-testid="growth-chart-svg-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
             style={{ width: '100%', height: '100%' }} aria-label="Business growth bar chart">
          {/* Horizontal grid */}
          {[0, 25, 50, 75].map((y) => (
            <line key={y} x1={0} x2={width} y1={(height * y) / 100} y2={(height * y) / 100}
                  stroke="var(--dash-divider)" strokeWidth={0.15} />
          ))}
          {rows.map((r, i) => {
            const xBase = i * groupW + (groupW - barW * 3) / 2;
            const drawBar = (v, idx, color) => {
              const h = (v / max) * (height - 6);
              return (
                <rect key={idx}
                      x={xBase + idx * barW}
                      y={height - h}
                      width={barW * 0.85}
                      height={Math.max(0.2, h)}
                      fill={color}
                      rx={0.4}
                      className="av2-bar"
                      style={{ animationDelay: `${i * 35}ms` }}>
                  <title>{`${r.m}: ${['Revenue','Leads','Fixes'][idx]} ${v}`}</title>
                </rect>
              );
            };
            return (
              <g key={r.m + i}>
                {drawBar(r.revenue, 0, '#FF6B00')}
                {drawBar(r.leads,   1, '#E8C86A')}
                {drawBar(r.fixes,   2, '#50C878')}
              </g>
            );
          })}
        </svg>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10,
                    color: 'var(--dash-text-faint)' }}>
        {rows.map((r) => <span key={r.m}>{r.m}</span>)}
      </div>
    </section>
  );
};

export default BusinessGrowthChart;
