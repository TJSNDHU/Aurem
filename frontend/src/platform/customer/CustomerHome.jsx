/**
 * CustomerHome — Redesigned to match the target "Obsidian Executive" design
 * (iter 322bj). Single data source: GET /api/me/home/dashboard.
 *
 * Sections (top → bottom):
 *  1. AUREM PULSE card — Total Revenue + delta · Website Health Score · Auto-Fix Live
 *     plus the 7-month mini bar chart in the top-right corner.
 *  2. BUSINESS GROWTH — multi-line chart (Revenue / Leads / Outreach / Pixel views / Auto-fixes).
 *  3. Triple footer: WEBSITE SCAN (4 dials) · ORA REPAIR EFFECT (% + sparkline) · SECURITY ALERTS.
 *
 * No mock data — every number is pulled from the live `/api/me/home/dashboard`.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, ShieldAlert, AlertTriangle } from 'lucide-react';
import {
  LineChart, Line, XAxis, ResponsiveContainer, Tooltip,
  AreaChart, Area, BarChart, Bar,
} from 'recharts';
import { getPlatformToken } from '../../utils/secureTokenStore';
import TrialBanner from '../TrialBanner';
import AuditWidget from './AuditWidget';

const API = process.env.REACT_APP_BACKEND_URL || '';

// ─── Tiny presentational atoms ──────────────────────────────────────
const GLASS = {
  background: 'linear-gradient(160deg, rgba(22,22,32,0.78) 0%, rgba(10,10,18,0.86) 100%)',
  backdropFilter: 'blur(22px) saturate(160%)',
  WebkitBackdropFilter: 'blur(22px) saturate(160%)',
  border: '1px solid rgba(212,175,55,0.14)',
  borderRadius: 18,
  boxShadow: '0 18px 44px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.04)',
};

function Card({ children, style, testid }) {
  return (
    <motion.div
      data-testid={testid}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 180, damping: 22 }}
      style={{ ...GLASS, padding: 22, ...style }}
    >
      {children}
    </motion.div>
  );
}

function SectionLabel({ children, dot }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      fontSize: 11, letterSpacing: '0.22em',
      color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase',
      fontFamily: "'Jost', sans-serif", fontWeight: 500, marginBottom: 18,
    }}>
      {dot && <span style={{ width: 7, height: 7, borderRadius: '50%',
                              background: '#3FCB7E', boxShadow: '0 0 8px #3FCB7E' }} />}
      {children}
    </div>
  );
}

function ProgressBar({ value, max = 100, gradient }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div style={{ width: '100%', height: 8, borderRadius: 99,
                  background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 1.1, ease: 'easeOut' }}
        style={{ height: '100%', borderRadius: 99, background: gradient }}
      />
    </div>
  );
}

function Dial({ value, label, sub, color }) {
  const pct = Math.max(0, Math.min(100, value));
  const r = 32;
  const c = 2 * Math.PI * r;
  const dash = c * (pct / 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ position: 'relative', width: 80, height: 80, flexShrink: 0 }}>
        <svg width="80" height="80" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r={r} fill="none"
                  stroke="rgba(255,255,255,0.07)" strokeWidth="6" />
          <motion.circle
            cx="40" cy="40" r={r} fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={`${dash} ${c}`}
            transform="rotate(-90 40 40)"
            initial={{ strokeDasharray: `0 ${c}` }}
            animate={{ strokeDasharray: `${dash} ${c}` }}
            transition={{ duration: 1.2, ease: 'easeOut' }}
            style={{ filter: `drop-shadow(0 0 6px ${color})` }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontFamily: "'Playfair Display', serif", fontSize: 22, color: '#F5E6C8',
        }}>{value}</div>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#9CA3AF', letterSpacing: '0.16em',
                       textTransform: 'uppercase', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 13, color: '#E8E0D0', marginTop: 4 }}>{sub}</div>
      </div>
    </div>
  );
}

const fmtCurrency = (n) => {
  if (!n) return '$0';
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${Math.round(n)}`;
};

// ─── Main ───────────────────────────────────────────────────────────
export default function CustomerHome({ ctx }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const tok = getPlatformToken();
        const r = await fetch(`${API}/api/me/home/dashboard`, {
          headers: { Authorization: `Bearer ${tok}` },
        });
        const j = await r.json();
        if (!cancelled) {
          if (r.ok) setData(j); else setErr(j.detail || 'Failed to load dashboard');
        }
      } catch (e) {
        if (!cancelled) setErr('Network error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // iter 322bg pixel hook — every Home view fires a 'page_view' event so the
  // founder's AUREM pixel tracks customer-portal engagement. The pixel script
  // is already loaded sitewide via index.html; we only emit the event here.
  useEffect(() => {
    try {
      if (typeof window !== 'undefined' && window.aurem && typeof window.aurem.track === 'function') {
        window.aurem.track('customer_home_view', {
          bin: ctx?.bin, plan: ctx?.plan, ts: Date.now(),
        });
      }
    } catch { /* pixel optional */ }
  }, [ctx]);

  const kpis = data?.kpis || {};
  const pulseBars = data?.pulse_bars || [];
  const scan = data?.scan || { geo: 0, sec: 0, acc: 0, seo: 0 };
  const repair = data?.repair || { success_pct: 0, healed: 0, attempts: 0, sparkline: [] };
  const alerts = data?.alerts || [];

  // Compose multi-line growth data
  const growth = useMemo(() => {
    const g = data?.growth;
    if (!g?.leads?.length) return [];
    return g.leads.map((row, i) => ({
      x: row.x,
      Revenue: g.revenue?.[i]?.y || 0,
      Leads: g.leads?.[i]?.y || 0,
      Outreach: g.outreach?.[i]?.y || 0,
      'Pixel views': g.pixel_views?.[i]?.y || 0,
      'Auto-fixes': g.auto_fixes?.[i]?.y || 0,
    }));
  }, [data]);

  const firstName = (ctx?.full_name || ctx?.name || '').split(' ')[0] || 'there';

  return (
    <div data-testid="customer-home" style={{ paddingBottom: 24 }}>
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 18 }}
      >
        <h1 style={{
          fontFamily: "'Cinzel', serif", fontSize: 30, fontWeight: 600,
          color: '#FFF', letterSpacing: '0.06em', margin: 0,
          textShadow: '0 0 22px rgba(249,115,22,0.28)',
        }}>HOME</h1>
        <div style={{ fontSize: 11, color: '#7A7468', fontFamily: "'JetBrains Mono', monospace" }}>
          {data?.generated_at ? `Updated ${new Date(data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : '...'}
        </div>
      </motion.div>

      <TrialBanner />

      {/* SEO + Ads Waste Audit widget (auto-runs on signup if URL captured) */}
      <div style={{ marginBottom: 18 }}>
        <AuditWidget />
      </div>

      {loading && (
        <div data-testid="home-loading" style={{ ...GLASS, padding: 36, textAlign: 'center', color: '#9CA3AF' }}>
          Loading your dashboard…
        </div>
      )}
      {err && !loading && (
        <div style={{ ...GLASS, padding: 24, color: '#FCA5A5' }}>
          {err}
        </div>
      )}

      {!loading && !err && data && (
        <>
          {/* ── AUREM PULSE — KPI hero card ───────────────────────── */}
          <Card testid="card-aurem-pulse" style={{ marginBottom: 18, padding: '26px 28px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 220px', gap: 26, alignItems: 'start' }}>
              <div>
                <SectionLabel dot>AUREM PULSE</SectionLabel>

                {/* Revenue row */}
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 18, flexWrap: 'wrap' }}>
                  <div style={{
                    fontFamily: "'Playfair Display', serif", fontSize: 44, fontWeight: 600,
                    color: '#F5E6C8', textShadow: '0 0 18px rgba(245,230,200,0.18)',
                    lineHeight: 1,
                  }} data-testid="kpi-revenue">{fmtCurrency(kpis.revenue_total)}</div>
                  <div style={{ color: kpis.revenue_delta_pct >= 0 ? '#3FCB7E' : '#F87171',
                                fontSize: 14, fontWeight: 500 }}>
                    {(kpis.revenue_delta_pct >= 0 ? '+' : '') + kpis.revenue_delta_pct}% {kpis.revenue_delta_pct >= 0 ? '↑' : '↓'}
                  </div>
                  <div style={{ color: kpis.revenue_delta_value >= 0 ? '#3FCB7E' : '#F87171',
                                fontSize: 14, fontWeight: 500 }}>
                    {(kpis.revenue_delta_value >= 0 ? '+' : '') + fmtCurrency(Math.abs(kpis.revenue_delta_value))}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: '#7A7468', letterSpacing: '0.16em',
                               textTransform: 'uppercase', marginTop: 6 }}>TOTAL REVENUE · LAST 30 DAYS</div>

                {/* Health + auto-fix progress row */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 26 }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                      <div style={{ fontSize: 11, color: '#9CA3AF', letterSpacing: '0.16em',
                                     textTransform: 'uppercase' }}>Website Health Score</div>
                      <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 24, color: '#F5E6C8' }}
                           data-testid="kpi-health-score">{kpis.health_score}<span style={{ color: '#5C5548', fontSize: 13 }}>/100</span></div>
                    </div>
                    <ProgressBar value={kpis.health_score} max={100}
                                 gradient="linear-gradient(90deg, #C9A227 0%, #F97316 100%)" />
                    <div style={{ fontSize: 10, color: '#5C5548', marginTop: 6, letterSpacing: '0.06em' }}>
                      composite of GEO · SEC · ACC · SEO
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                      <div style={{ fontSize: 11, color: '#9CA3AF', letterSpacing: '0.16em',
                                     textTransform: 'uppercase' }}>Auto-Fix Live</div>
                      <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 24, color: '#F5E6C8' }}
                           data-testid="kpi-autofix">
                        {kpis.auto_fix_today}<span style={{ color: '#5C5548', fontSize: 13 }}>/{kpis.auto_fix_target}</span>
                      </div>
                    </div>
                    <ProgressBar value={kpis.auto_fix_today} max={kpis.auto_fix_target}
                                 gradient="linear-gradient(90deg, #2BB36C 0%, #3FCB7E 100%)" />
                    <div style={{ fontSize: 10, color: '#5C5548', marginTop: 6, letterSpacing: '0.06em' }}>
                      ORA patches applied today
                    </div>
                  </div>
                </div>
              </div>

              {/* Top-right mini bar chart (7 months) */}
              <div style={{ height: 130 }}>
                <div style={{ fontSize: 10, color: '#5C5548', letterSpacing: '0.16em',
                               textTransform: 'uppercase', textAlign: 'right', marginBottom: 6 }}>
                  Active · last 7 mo
                </div>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={pulseBars} barCategoryGap="20%">
                    <XAxis dataKey="month" tick={{ fontSize: 9, fill: '#7A7468' }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: 'rgba(249,115,22,0.06)' }}
                             contentStyle={{ background: '#0F0F18', border: '1px solid rgba(212,175,55,0.18)', borderRadius: 8, fontSize: 11 }} />
                    <Bar dataKey="value" fill="url(#barGold)" radius={[3, 3, 0, 0]} />
                    <defs>
                      <linearGradient id="barGold" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#F5E6C8" />
                        <stop offset="100%" stopColor="#8B7355" />
                      </linearGradient>
                    </defs>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Card>

          {/* ── BUSINESS GROWTH multi-line chart ─────────────────── */}
          <Card testid="card-business-growth" style={{ marginBottom: 18, padding: '26px 28px' }}>
            <SectionLabel>BUSINESS GROWTH</SectionLabel>
            <div style={{ height: 260 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={growth} margin={{ top: 10, right: 18, left: -10, bottom: 0 }}>
                  <XAxis dataKey="x" tick={{ fontSize: 10, fill: '#7A7468' }}
                         axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#0F0F18', border: '1px solid rgba(212,175,55,0.18)',
                                    borderRadius: 8, fontSize: 11 }}
                  />
                  <Line type="monotone" dataKey="Revenue"     stroke="#F5E6C8" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Leads"       stroke="#F97316" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Outreach"    stroke="#C9A227" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Pixel views" stroke="#9CA3AF" strokeWidth={1.5} dot={false} strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="Auto-fixes"  stroke="#3FCB7E" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Legend chips */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 12, fontSize: 11 }}>
              {[
                ['Revenue', '#F5E6C8'], ['Leads', '#F97316'], ['Outreach', '#C9A227'],
                ['Pixel views', '#9CA3AF'], ['Auto-fixes', '#3FCB7E'],
              ].map(([k, c]) => (
                <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
                                        color: '#9CA3AF', letterSpacing: '0.06em' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: c }} />{k}
                </span>
              ))}
            </div>
          </Card>

          {/* ── Triple footer: Scan · Repair · Alerts ─────────────── */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 18 }}>
            {/* Website Scan dials */}
            <Card testid="card-website-scan">
              <SectionLabel>WEBSITE SCAN</SectionLabel>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <Dial value={scan.geo} label="GEO" sub="Geographic reach" color="#C9A227" />
                <Dial value={scan.sec} label="SEC" sub="TLS · CSP"        color="#3FCB7E" />
                <Dial value={scan.acc} label="ACC" sub="WCAG · ARIA"      color="#F97316" />
                <Dial value={scan.seo} label="SEO" sub="LCP · meta"       color="#60A5FA" />
              </div>
            </Card>

            {/* ORA Repair Effect */}
            <Card testid="card-ora-repair-effect">
              <SectionLabel>ORA REPAIR EFFECT</SectionLabel>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
                <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 38, color: '#F5E6C8' }}
                     data-testid="repair-success-pct">{repair.success_pct}<span style={{ fontSize: 16, color: '#7A7468' }}>%</span></div>
                <div style={{ color: '#3FCB7E', fontSize: 12, fontWeight: 600 }}>success</div>
              </div>
              <div style={{ fontSize: 11, color: '#7A7468', letterSpacing: '0.06em', marginBottom: 14 }}>
                {repair.healed} healed · {repair.attempts} attempts (14d)
              </div>
              <div style={{ height: 90 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={(repair.sparkline || []).map((y, i) => ({ x: i, y }))}>
                    <defs>
                      <linearGradient id="repairGreen" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3FCB7E" stopOpacity={0.5} />
                        <stop offset="100%" stopColor="#3FCB7E" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="y" stroke="#3FCB7E" strokeWidth={2} fill="url(#repairGreen)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {/* Security alerts list */}
            <Card testid="card-security-alerts">
              <SectionLabel>SECURITY ALERTS</SectionLabel>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 12 }}>
                <div style={{ fontFamily: "'Playfair Display', serif", fontSize: 38, color: '#F5E6C8' }}
                     data-testid="alerts-total">{alerts.length}</div>
                <div style={{ color: '#7A7468', fontSize: 11, letterSpacing: '0.16em',
                               textTransform: 'uppercase' }}>recent</div>
              </div>
              {alerts.length === 0 ? (
                <div style={{ color: '#5C5548', fontSize: 12 }}>No alerts in the last 48h.</div>
              ) : (
                <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                  {alerts.slice(0, 5).map((a, i) => {
                    const lv = (a.level || 'low').toUpperCase();
                    const color = lv === 'HIGH' ? '#F87171' : lv === 'MED' || lv === 'MEDIUM' ? '#FBBF24' : '#9CA3AF';
                    return (
                      <li key={i} style={{ display: 'flex', alignItems: 'center', gap: 8,
                                            padding: '5px 0', fontSize: 12, color: '#E8E0D0' }}>
                        <span style={{ fontSize: 9, padding: '2px 5px', borderRadius: 4,
                                        background: `${color}22`, color: color, fontWeight: 700,
                                        letterSpacing: '0.06em' }}>{lv}</span>
                        <span style={{ flex: 1, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}>
                          {a.message}
                        </span>
                        <span style={{ fontSize: 10, color: '#5C5548' }}>
                          {a.ts_utc ? new Date(a.ts_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
          </div>

          {/* Subtle hint for next iter — visible only when data is bare */}
          {kpis.revenue_total === 0 && repair.attempts === 0 && (
            <div style={{ marginTop: 18, padding: '12px 16px', borderRadius: 10,
                          border: '1px dashed rgba(249,115,22,0.18)',
                          background: 'rgba(249,115,22,0.04)', display: 'flex',
                          alignItems: 'center', gap: 10, fontSize: 12, color: '#B8AE9F' }}>
              <Activity size={14} color="#F97316" />
              Hi {firstName} — your AUREM swarm is warming up. Numbers will populate as scans and Stripe activity flow in.
            </div>
          )}
        </>
      )}
    </div>
  );
}
