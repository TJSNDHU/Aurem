/**
 * BusinessGrowthChart — multi-line growth chart (iter 332b D-22).
 *
 * Founder ask: "Business Growth must show colorful lines".
 *
 * Renders 5 series — Leads, Revenue, Auto-fixes, Outreach, Pixel Views —
 * as smooth SVG paths with a soft gradient fill under each. Empty data
 * just draws a calm flat baseline so the card never looks broken.
 *
 * Props:
 *   series: [{ m, revenue, leads, fixes, outreach, pixel }, ...]
 */
import React, { useMemo } from 'react';

const SERIES = [
  { k: 'leads',    label: 'Leads',      color: '#60A5FA' },  // sky-blue
  { k: 'revenue',  label: 'Revenue',    color: '#F97316' },  // orange (brand)
  { k: 'fixes',    label: 'Auto-fixes', color: '#34D399' },  // emerald
  { k: 'outreach', label: 'Outreach',   color: '#E879F9' },  // fuchsia
  { k: 'pixel',    label: 'Pixel',      color: '#FBBF24' },  // amber
];

const FALLBACK_MONTHS = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May'];

// Catmull-Rom → cubic Bézier for a smooth, "premium" curve through the points.
function smoothPath(pts) {
  if (pts.length < 2) return '';
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
  }
  return d;
}

export const BusinessGrowthChart = ({ series = [] }) => {
  const rows = useMemo(() => {
    if (!series || series.length === 0) {
      return FALLBACK_MONTHS.map((m) => ({
        m, revenue: 0, leads: 0, fixes: 0, outreach: 0, pixel: 0,
      }));
    }
    return series.slice(-9).map((d) => ({
      m:        String(d.m || '').slice(0, 3),
      revenue:  Number(d.revenue  ?? d.a ?? 0),
      leads:    Number(d.leads    ?? d.b ?? 0),
      fixes:    Number(d.fixes    ?? d.c ?? 0),
      outreach: Number(d.outreach ?? 0),
      pixel:    Number(d.pixel    ?? d.pixel_views ?? 0),
    }));
  }, [series]);

  const max = Math.max(
    1,
    ...rows.flatMap((r) => SERIES.map((s) => r[s.k] || 0)),
  );

  const W = 100, H = 60;
  const xFor = (i) => (i / Math.max(1, rows.length - 1)) * W;
  const yFor = (v) => H - (v / max) * (H - 6) - 3;

  return (
    <section data-testid="growth-card" className="av2-card"
             style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between',
                        alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600,
                      color: 'var(--dash-text)' }}>
          Business Growth
        </h3>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap',
                      fontSize: 11, color: 'var(--dash-text-muted)' }}
             data-testid="growth-legend">
          {SERIES.map((s) => (
            <span key={s.k}
                  data-testid={`growth-legend-${s.k}`}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 3, borderRadius: 2,
                              background: s.color, display: 'inline-block' }} />
              {s.label}
            </span>
          ))}
        </div>
      </header>
      <div style={{ width: '100%', height: 220, position: 'relative' }}
           data-testid="growth-chart-svg-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
             style={{ width: '100%', height: '100%' }}
             aria-label="Business growth multi-line chart">
          <defs>
            {SERIES.map((s) => (
              <linearGradient key={s.k} id={`growth-grad-${s.k}`}
                              x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%"   stopColor={s.color} stopOpacity="0.30" />
                <stop offset="100%" stopColor={s.color} stopOpacity="0" />
              </linearGradient>
            ))}
          </defs>

          {/* Horizontal grid */}
          {[0, 25, 50, 75].map((y) => (
            <line key={y} x1={0} x2={W}
                  y1={(H * y) / 100} y2={(H * y) / 100}
                  stroke="var(--dash-divider)" strokeWidth={0.12} />
          ))}

          {/* One smooth path + soft fill per series */}
          {SERIES.map((s) => {
            const pts = rows.map((r, i) => ({ x: xFor(i), y: yFor(r[s.k] || 0) }));
            const linePath = smoothPath(pts);
            const fillPath = `${linePath} L ${pts[pts.length - 1].x} ${H} L ${pts[0].x} ${H} Z`;
            return (
              <g key={s.k} data-testid={`growth-line-${s.k}`}>
                <path d={fillPath} fill={`url(#growth-grad-${s.k})`} stroke="none" />
                <path d={linePath} fill="none"
                      stroke={s.color} strokeWidth="0.8"
                      strokeLinecap="round" strokeLinejoin="round"
                      style={{ filter: `drop-shadow(0 0 1px ${s.color}55)` }} />
                {pts.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r="0.6"
                           fill={s.color}
                           data-testid={`growth-point-${s.k}-${i}`}>
                    <title>{`${rows[i].m} · ${s.label}: ${rows[i][s.k]}`}</title>
                  </circle>
                ))}
              </g>
            );
          })}
        </svg>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                     fontSize: 10, color: 'var(--dash-text-faint)' }}>
        {rows.map((r, i) => <span key={r.m + i}>{r.m}</span>)}
      </div>
    </section>
  );
};

export default BusinessGrowthChart;
