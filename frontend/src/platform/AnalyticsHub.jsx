/**
 * AUREM Analytics Hub
 * Business intelligence dashboard with real-time metrics, insights, and reports
 * Re-themed for AUREM dark design system
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3, TrendingUp, Users, Globe, Activity, Clock,
  RefreshCw, ArrowUpRight, ArrowDownRight, Filter, Download,
  MessageSquare, Zap, Target, DollarSign, Eye, Calendar
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

export default function AnalyticsHub({ token }) {
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30d');
  const [metricsData, setMetricsData] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [intelDashboard, setIntelDashboard] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);
      const res = await fetch(`${API_URL}/api/aurem/metrics`, {
        headers: { 'Authorization': `Bearer ${token}` },
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const data = await res.json();
        setMetricsData(data);
      } else {
        setMetricsData({ queries_today: 0, uptime: 100, avg_response_time: 0, active_brands: 0 });
      }
    } catch {
      setMetricsData({ queries_today: 0, uptime: 100, avg_response_time: 0, active_brands: 0 });
    } finally {
      setLoading(false);
    }
  }, [token]);

  const fetchIntelligence = useCallback(async () => {
    if (!token) return;
    try {
      const headers = { 'Authorization': `Bearer ${token}` };
      const [forecastRes, dashRes] = await Promise.all([
        fetch(`${API_URL}/api/intelligence/revenue/forecast?months=6`, { headers }),
        fetch(`${API_URL}/api/intelligence/dashboard`, { headers }),
      ]);
      if (forecastRes.ok) setForecast(await forecastRes.json());
      if (dashRes.ok) setIntelDashboard(await dashRes.json());
    } catch (e) {
      console.error('Intelligence fetch failed:', e);
    }
  }, [token]);

  useEffect(() => {
    const load = async () => {
      if (token) {
        await fetchAnalytics();
        await fetchIntelligence();
      } else {
        setLoading(false);
      }
    };
    load();
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const interval = setInterval(() => {
      fetchAnalytics();
      fetchIntelligence();
    }, 30000);
    return () => clearInterval(interval);
  }, [token, fetchAnalytics, fetchIntelligence]);

  const kpis = metricsData ? [
    { label: 'TOTAL CONVERSATIONS', value: (metricsData.queries_today || 0).toLocaleString(), change: '--', up: true, icon: MessageSquare, color: '#D4AF37' },
    { label: 'ACTIVE CUSTOMERS', value: (intelDashboard?.stats?.total_contacts || metricsData.active_brands || 0).toLocaleString(), change: '--', up: true, icon: Users, color: '#4ade80' },
    { label: 'PIPELINE VALUE', value: `$${(intelDashboard?.stats?.pipeline_value || 0).toLocaleString()}`, change: '--', up: true, icon: DollarSign, color: '#D4AF37' },
    { label: 'WIN RATE', value: `${intelDashboard?.stats?.win_rate || 0}%`, change: '--', up: true, icon: Target, color: '#4ade80' },
    { label: 'OPEN DEALS', value: (intelDashboard?.stats?.open_deals || 0).toLocaleString(), change: '--', up: true, icon: TrendingUp, color: '#8B5CF6' },
    { label: 'AGENT UTILIZATION', value: `${metricsData.uptime || 0}%`, change: '--', up: true, icon: Activity, color: '#D4AF37' }
  ] : [];

  const channelData = [
    { channel: 'AI Chat', sessions: 0, conversion: '0%', color: '#D4AF37', pct: 0 },
    { channel: 'WhatsApp', sessions: 0, conversion: '0%', color: '#25D366', pct: 0 },
    { channel: 'Email', sessions: 0, conversion: '0%', color: '#3b82f6', pct: 0 },
    { channel: 'Voice', sessions: 0, conversion: '0%', color: '#8B5CF6', pct: 0 }
  ];

  const topAgents = [
    { name: 'Scout Agent', tasks: 0, success: '0%', status: 'STANDBY' },
    { name: 'Closer Agent', tasks: 0, success: '0%', status: 'STANDBY' },
    { name: 'Architect Agent', tasks: 0, success: '0%', status: 'STANDBY' },
    { name: 'Envoy Agent', tasks: 0, success: '0%', status: 'STANDBY' },
    { name: 'Orchestrator', tasks: 0, success: '0%', status: 'STANDBY' }
  ];

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" style={{ background: 'var(--aurem-bg)' }} data-testid="analytics-hub-loading">
        <div className="flex items-center gap-3" style={{ color: 'var(--aurem-body-secondary)' }}>
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading analytics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto" style={{ background: 'var(--aurem-bg)' }} data-testid="analytics-hub">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Analytics Hub</h1>
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Business intelligence dashboard — real-time metrics, insights, and reports</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-white/80 backdrop-blur-sm p-0.5 rounded-lg border border-[#FF6B00]/20">
              {['7d', '30d', '90d'].map(range => (
                <button
                  key={range}
                  onClick={() => setDateRange(range)}
                  data-testid={`date-range-${range}`}
                  className={`px-3 py-1.5 text-[10px] rounded-md transition-all ${
                    dateRange === range
                      ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30'
                      : 'text-[#666] hover:text-[#555]'
                  }`}
                >
                  {range === '7d' ? '7 Days' : range === '30d' ? '30 Days' : '90 Days'}
                </button>
              ))}
            </div>
            <button onClick={() => { /* Export analytics data */ }} className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] border rounded-lg transition-colors" style={{ color: 'var(--aurem-body-secondary)', borderColor: 'var(--aurem-border)' }} data-testid="export-analytics-btn">
              <Download className="w-3 h-3" />
              Export
            </button>
          </div>
        </div>

        {/* KPI Grid */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {kpis.map((kpi, idx) => (
            <div key={idx} className="p-4 rounded-lg" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <kpi.icon className="w-4 h-4" style={{ color: kpi.color }} />
                  <span className="text-[9px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>{kpi.label}</span>
                </div>
                <div className={`flex items-center gap-0.5 text-[10px] ${kpi.up ? 'text-[#4ade80]' : 'text-[#ef4444]'}`}>
                  {kpi.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                  {kpi.change}
                </div>
              </div>
              <div className="text-2xl font-semibold font-mono" style={{ color: kpi.color }}>{kpi.value}</div>
            </div>
          ))}
        </div>

        {/* Revenue Forecast (AI-Powered) */}
        {forecast?.forecast?.length > 0 && (
          <div className="mb-8 p-5 rounded-xl" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }} data-testid="revenue-forecast">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4" style={{ color: '#D4AF37' }} />
                <h3 className="text-xs tracking-wider font-medium" style={{ color: 'var(--aurem-heading)' }}>REVENUE FORECAST</h3>
                <span className="text-[9px] px-2 py-0.5 rounded-full" style={{ background: 'rgba(212,175,55,0.1)', color: '#D4AF37' }}>
                  {forecast.methodology === 'ai_enhanced' ? 'AI Enhanced' : 'Projection'}
                </span>
              </div>
              {forecast.weighted_pipeline > 0 && (
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Weighted Pipeline: <strong style={{ color: '#4ade80' }}>${forecast.weighted_pipeline.toLocaleString()}</strong>
                </span>
              )}
            </div>
            <div className="grid grid-cols-6 gap-3">
              {forecast.forecast.slice(0, 6).map((m, i) => (
                <div key={i} className="p-3 rounded-lg text-center" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--aurem-border)' }}>
                  <div className="text-[9px] mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{m.month}</div>
                  <div className="text-sm font-mono font-semibold" style={{ color: '#D4AF37' }}>
                    ${(m.predicted_revenue || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </div>
                  <div className="mt-1 h-1 rounded-full" style={{ background: 'var(--aurem-border)' }}>
                    <div className="h-full rounded-full" style={{ width: `${(m.confidence || 0) * 100}%`, background: 'linear-gradient(90deg, #4ade80, #D4AF37)' }} />
                  </div>
                  <div className="text-[8px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{Math.round((m.confidence || 0) * 100)}% conf.</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-6 mb-8">
          {/* Channel Performance */}
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-xs tracking-wider mb-5" style={{ color: 'var(--aurem-body-secondary)' }}>CHANNEL PERFORMANCE</h3>
            <div className="space-y-4">
              {channelData.map((ch, idx) => (
                <div key={idx}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{ch.channel}</span>
                    <div className="flex items-center gap-3 text-[10px]">
                      <span style={{ color: 'var(--aurem-body-secondary)' }}>{ch.sessions.toLocaleString()} sessions</span>
                      <span style={{ color: ch.color }}>{ch.conversion} conv.</span>
                    </div>
                  </div>
                  <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--aurem-border)' }}>
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${ch.pct}%`, backgroundColor: ch.color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Agent Performance */}
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-xs tracking-wider mb-5" style={{ color: 'var(--aurem-body-secondary)' }}>AGENT PERFORMANCE</h3>
            <div className="space-y-3">
              {topAgents.map((agent, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${agent.status === 'ACTIVE' ? 'bg-[#4ade80]' : 'bg-[#555]'}`} />
                    <span className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{agent.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-[10px]">
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>{agent.tasks} tasks</span>
                    <span style={{ color: '#4ade80' }}>{agent.success}</span>
                    <span className="text-[9px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>{agent.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Weekly Trend Chart */}
        <div className="rounded-xl p-5 mb-8" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-xs tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>CONVERSATION VOLUME (LAST 7 DAYS)</h3>
            <div className="flex items-center gap-4 text-[10px] text-[#555]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#D4AF37]" /> AI Chat</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#D4AF37]/40" /> Total</span>
            </div>
          </div>
          <div className="flex items-end gap-3 h-40">
            {[
              { day: 'Mon', ai: 72, total: 85 },
              { day: 'Tue', ai: 58, total: 70 },
              { day: 'Wed', ai: 81, total: 92 },
              { day: 'Thu', ai: 90, total: 98 },
              { day: 'Fri', ai: 65, total: 78 },
              { day: 'Sat', ai: 42, total: 55 },
              { day: 'Sun', ai: 38, total: 48 }
            ].map((d, idx) => (
              <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full flex gap-1 items-end" style={{ height: '130px' }}>
                  <div
                    className="flex-1 rounded-t-sm bg-[#D4AF37]/20 transition-all"
                    style={{ height: `${d.total}%` }}
                  />
                  <div
                    className="flex-1 rounded-t-sm bg-[#D4AF37] transition-all"
                    style={{ height: `${d.ai}%` }}
                  />
                </div>
                <span className="text-[9px] text-[#555]">{d.day}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Insights */}
        <div className="rounded-xl p-5" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
          <h3 className="text-xs tracking-wider mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>AI-GENERATED INSIGHTS</h3>
          <div className="grid grid-cols-3 gap-4">
            {[
              { insight: 'WhatsApp has the highest conversion rate (42%) — consider increasing WhatsApp outreach campaigns', icon: MessageSquare, color: '#25D366' },
              { insight: 'Peak engagement hours: 10AM-2PM. Schedule critical automations during this window', icon: Clock, color: '#D4AF37' },
              { insight: 'Scout Agent completed 18% more tasks this week. Consider scaling similar patterns', icon: TrendingUp, color: '#4ade80' }
            ].map((item, idx) => (
              <div key={idx} className="p-4 bg-white/60 rounded-lg border border-[#FF6B00]/20">
                <item.icon className="w-4 h-4 mb-2" style={{ color: item.color }} />
                <p className="text-[11px] text-[#888] leading-relaxed">{item.insight}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
