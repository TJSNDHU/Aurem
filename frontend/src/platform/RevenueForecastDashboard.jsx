import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { DollarSign, TrendingUp, TrendingDown, RefreshCw, Loader2, AlertTriangle, Target, Layers, CreditCard, Rocket, Zap, BarChart3 } from 'lucide-react';
import { motion, StaggerGrid, MotionCard, PageTransition, cardVariant } from './motion-system';

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = (n) => n >= 1000 ? `$${(n/1000).toFixed(1)}k` : `$${n.toFixed(0)}`;

export default function RevenueForecastDashboard({ token }) {
  const [forecast, setForecast] = useState(null);
  const [briefLine, setBriefLine] = useState('');
  const [loading, setLoading] = useState(true);
  const [conversionMetrics, setConversionMetrics] = useState(null);
  const [oracleTrend, setOracleTrend] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [fcRes, blRes, cmRes] = await Promise.all([
        fetch(`${API}/api/revenue-forecast/90day?tenant_id=aurem_platform`, { headers }),
        fetch(`${API}/api/revenue-forecast/brief-line?tenant_id=aurem_platform`, { headers }),
        fetch(`${API}/api/proximity/conversion-metrics`, { headers }),
      ]);
      if (fcRes.ok) setForecast(await fcRes.json());
      if (blRes.ok) { const d = await blRes.json(); setBriefLine(d.brief_line || ''); }
      if (cmRes.ok) setConversionMetrics(await cmRes.json());

      // Fetch oracle trend from chat status endpoint
      try {
        const tRes = await fetch(`${API}/api/aurem/chat`, {
          method: 'POST', headers,
          body: JSON.stringify({ message: '__internal_trend_check__', session_id: 'trend_probe' }),
        });
        // We don't use this — trend comes from the oracle_proactive service
      } catch {}
    } catch (e) { console.error('Revenue forecast:', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 className="size-6 animate-spin" style={{ color: 'var(--aurem-body-secondary)' }} />
    </div>
  );

  const s = forecast?.summary || {};
  const p = forecast?.pipeline || {};
  const r = forecast?.recurring || {};
  const pend = forecast?.pending || {};
  const projected = s.projected_revenue || 0;
  const atRisk = s.revenue_at_risk || 0;
  const totalPotential = (projected + atRisk) || 1;
  const riskPct = Math.round((atRisk / totalPotential) * 100 * 10) / 10;

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="revenue-forecast-dashboard">
      <PageTransition>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-lg font-bold" style={{ color: 'var(--aurem-heading)' }}>90-Day Revenue Forecast</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
              Pipeline weighted + recurring + pending recovery
            </p>
          </div>
          <button onClick={() => { setLoading(true); fetchData(); }} className="p-2 rounded-lg hover:bg-white/10 transition-colors" data-testid="refresh-forecast">
            <RefreshCw className="size-4" style={{ color: 'var(--aurem-body-secondary)' }} />
          </button>
        </div>

        {/* Hero metric */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            className="aurem-glass-card p-6" data-testid="projected-revenue">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="size-5" style={{ color: '#22C55E' }} />
              <span className="text-xs font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Projected Revenue (90d)</span>
            </div>
            <div className="text-3xl font-black" style={{ color: '#22C55E' }}>{fmt(projected)}</div>
            <div className="text-[10px] mt-1 px-2 py-0.5 rounded-full inline-block" style={{
              background: 'rgba(34,197,94,0.1)', color: '#22C55E',
            }}>Confidence: {s.confidence || 'low'}</div>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1 }}
            className="aurem-glass-card p-6" data-testid="revenue-at-risk">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="size-5" style={{ color: '#EF4444' }} />
              <span className="text-xs font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Revenue at Risk</span>
            </div>
            <div className="text-3xl font-black" style={{ color: '#EF4444' }}>{fmt(atRisk)}</div>
            <div className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
              Unrealized pipeline + unpaid pending
            </div>
          </motion.div>
        </div>

        {/* Breakdown */}
        <StaggerGrid className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <MotionCard variant={cardVariant} className="aurem-glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Target className="size-4" style={{ color: '#3B82F6' }} />
              <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Pipeline</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Active Leads</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{p.active_leads || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Total Value</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{fmt(p.total_value || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Win Prob</span>
                <span className="text-xs font-bold" style={{ color: '#3B82F6' }}>{((p.avg_win_probability || 0) * 100).toFixed(0)}%</span>
              </div>
              <div className="pt-2 border-t" style={{ borderColor: 'rgba(61,58,57,0.25)' }}>
                <div className="flex justify-between">
                  <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Weighted</span>
                  <span className="text-sm font-black" style={{ color: '#3B82F6' }}>{fmt(p.weighted_value || 0)}</span>
                </div>
              </div>
            </div>
          </MotionCard>

          <MotionCard variant={cardVariant} className="aurem-glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="size-4" style={{ color: '#22C55E' }} />
              <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Recurring</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Orders (90d)</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{r.completed_orders_90d || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Avg Invoice</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{fmt(r.avg_invoice || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Monthly</span>
                <span className="text-xs font-bold" style={{ color: '#22C55E' }}>{fmt(r.monthly_recurring || 0)}</span>
              </div>
              <div className="pt-2 border-t" style={{ borderColor: 'rgba(61,58,57,0.25)' }}>
                <div className="flex justify-between">
                  <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>90-Day</span>
                  <span className="text-sm font-black" style={{ color: '#22C55E' }}>{fmt(r.projected_90d || 0)}</span>
                </div>
              </div>
            </div>
          </MotionCard>

          <MotionCard variant={cardVariant} className="aurem-glass-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <CreditCard className="size-4" style={{ color: '#F97316' }} />
              <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Pending Recovery</span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Pending Orders</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{pend.pending_orders || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Total Pending</span>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{fmt(pend.pending_total || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Payment Rate</span>
                <span className="text-xs font-bold" style={{ color: '#F97316' }}>{((pend.historical_payment_rate || 0) * 100).toFixed(0)}%</span>
              </div>
              <div className="pt-2 border-t" style={{ borderColor: 'rgba(61,58,57,0.25)' }}>
                <div className="flex justify-between">
                  <span className="text-[10px] font-bold" style={{ color: 'var(--aurem-body-secondary)' }}>Expected</span>
                  <span className="text-sm font-black" style={{ color: '#F97316' }}>{fmt(pend.expected_recovery || 0)}</span>
                </div>
              </div>
            </div>
          </MotionCard>
        </StaggerGrid>

        {/* Morning brief line */}
        {briefLine && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
            className="aurem-glass-card p-4 mb-4" data-testid="forecast-brief-line">
            <div className="text-[10px] font-bold mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Morning Brief Line</div>
            <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{briefLine}</p>
          </motion.div>
        )}

        {/* Context Overlay + Growth Opportunity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 }}
            className="aurem-glass-card p-5" data-testid="context-overlay-card"
            style={{ border: '1px solid rgba(255,107,0,0.12)' }}>
            <div className="flex items-center gap-2 mb-3">
              <div className="size-8 rounded-lg flex items-center justify-center" style={{
                background: 'rgba(255,107,0,0.08)', border: '1px solid rgba(255,107,0,0.15)',
              }}>
                <Rocket className="size-4 text-[#FF6B00]" />
              </div>
              <div>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Context Overlay</span>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Forward-Loop from Scout</div>
              </div>
              <span className="ml-auto px-2 py-0.5 rounded-full text-[8px] font-bold" style={{
                background: 'rgba(255,107,0,0.08)', color: '#FF6B00',
              }}>GROWTH OPPORTUNITY</span>
            </div>
            {riskPct > 10 ? (
              <div className="p-3 rounded-lg mb-2" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)' }}>
                <p className="text-xs font-medium" style={{ color: '#EF4444' }}>
                  {riskPct}% revenue at risk. Recommend a 15km Proximity Blast to fill the gap.
                </p>
              </div>
            ) : (
              <div className="p-3 rounded-lg mb-2" style={{ background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.12)' }}>
                <p className="text-xs font-medium" style={{ color: '#22C55E' }}>
                  Revenue risk is within safe range ({riskPct}%). Pipeline health looks good.
                </p>
              </div>
            )}
            <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
              Trending sectors in your area will appear here as Scout discovers local leads.
            </p>
          </motion.div>

          {/* Conversion Feedback Tracker */}
          <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.5 }}
            className="aurem-glass-card p-5" data-testid="conversion-tracker-card">
            <div className="flex items-center gap-2 mb-3">
              <div className="size-8 rounded-lg flex items-center justify-center" style={{
                background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.15)',
              }}>
                <BarChart3 className="size-4 text-[#3B82F6]" />
              </div>
              <div>
                <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Envoy Performance</span>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Conversion Feedback Loop</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center">
                <div className="text-lg font-black" style={{ color: 'var(--aurem-heading)' }}>
                  {conversionMetrics?.total_outreach || 0}
                </div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Total Outreach</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-black" style={{ color: '#3B82F6' }}>
                  {((conversionMetrics?.response_rate || 0) * 100).toFixed(0)}%
                </div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Response Rate</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-black" style={{ color: '#22C55E' }}>
                  {((conversionMetrics?.conversion_rate || 0) * 100).toFixed(0)}%
                </div>
                <div className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>Conversion Rate</div>
              </div>
            </div>
            <p className="text-[9px] mt-3 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>
              {conversionMetrics?.total_outreach > 0
                ? 'Envoy response data feeds back into Oracle win probability calculations.'
                : 'Deploy Envoy outreach to start tracking conversion performance.'}
            </p>
          </motion.div>
        </div>
      </PageTransition>
    </div>
  );
}
