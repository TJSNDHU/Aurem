/**
 * AUREM Voice Agent Analytics Dashboard
 * Scientific-Luxe / Veridian Oasis Theme
 * 
 * Features:
 * - Call Volume Trends (7-day sparkline)
 * - VIP vs Standard Tier Breakdown (donut)
 * - Sentiment Analysis Breakdown
 * - Average Duration by Persona
 * - Action Conversion Funnel
 * - Cost Savings Calculator
 * - Live Call Status
 */

import { useState, useEffect, useCallback } from "react";
import {
  Phone, PhoneCall, TrendingUp, Users, Clock, Zap, DollarSign,
  PieChart, BarChart2, Activity, Award, Target, RefreshCw,
  Smile, Meh, Frown, Radio, ArrowUpRight, ArrowDownRight
} from "lucide-react";
import '../theme/aurem-green.css';

const COPPER = "#FF6B00";
const COPPER2 = "#CC5500";
const FOREST = "#0A0A0C";
const TEXT = "#E8E6E3";
const TEXT_SEC = "rgba(255,255,255,0.55)";
const TEXT_MUTED = "rgba(255,255,255,0.35)";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

/* ═══ MINI CHART COMPONENTS ═══ */

function SparklineChart({ data, color = COPPER, height = 40 }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - ((val - min) / range) * 80 - 10;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width="100%" height={height} viewBox="0 0 100 100" preserveAspectRatio="none">
      <defs>
        <linearGradient id={`sg-${color.replace("#","")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
      <polygon points={`0,100 ${points} 100,100`} fill={`url(#sg-${color.replace("#","")})`} />
    </svg>
  );
}

function DonutChart({ data, size = 120 }) {
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;
  let currentAngle = -90;
  const segments = data.map((d) => {
    const angle = (d.value / total) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;
    const startRad = (startAngle * Math.PI) / 180;
    const endRad = ((startAngle + angle) * Math.PI) / 180;
    const x1 = 50 + 40 * Math.cos(startRad);
    const y1 = 50 + 40 * Math.sin(startRad);
    const x2 = 50 + 40 * Math.cos(endRad);
    const y2 = 50 + 40 * Math.sin(endRad);
    const largeArc = angle > 180 ? 1 : 0;
    return {
      path: `M 50 50 L ${x1} ${y1} A 40 40 0 ${largeArc} 1 ${x2} ${y2} Z`,
      color: d.color, label: d.label, value: d.value,
      percent: ((d.value / total) * 100).toFixed(0)
    };
  });

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox="0 0 100 100">
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} opacity={0.85} />
        ))}
        <circle cx="50" cy="50" r="25" fill="rgba(255,255,255,0.85)" />
        <text x="50" y="54" textAnchor="middle" fill={FOREST} fontSize="14" fontWeight="600">{total}</text>
      </svg>
      <div>
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-2 mb-1">
            <div className="size-2.5 rounded-sm" style={{ background: seg.color }} />
            <span className="text-[11px]" style={{ color: TEXT_SEC }}>{seg.label}</span>
            <span className="text-[11px] ml-auto" style={{ color: TEXT_MUTED }}>{seg.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HorizontalBar({ label, value, maxValue, color = COPPER }) {
  const percent = maxValue > 0 ? (value / maxValue) * 100 : 0;
  return (
    <div className="mb-3">
      <div className="flex justify-between mb-1">
        <span className="text-xs" style={{ color: TEXT_SEC }}>{label}</span>
        <span className="text-xs font-mono" style={{ color: COPPER2 }}>{value}s</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(26,48,38,0.08)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{
          width: `${percent}%`,
          background: `linear-gradient(90deg, ${color}, ${color}80)`,
        }} />
      </div>
    </div>
  );
}

/* ═══ STAT CARD ═══ */

function StatCard({ label, value, subValue, icon: Icon, trend, color = COPPER, sparkData }) {
  const trendUp = trend > 0;
  const trendColor = trend > 0 ? "#16a34a" : trend < 0 ? "#dc2626" : TEXT_MUTED;

  return (
    <div className="aurem-glass-card p-4" data-testid={`stat-${label.toLowerCase().replace(/\s/g,'-')}`}>
      <div className="flex items-start gap-3">
        <div className="size-10 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${color}15` }}>
          <Icon size={20} color={color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: TEXT_MUTED, fontFamily: "'Montserrat', sans-serif" }}>{label}</div>
          <div className="text-2xl font-light font-mono" style={{ color: FOREST }}>{value}</div>
          {subValue && <div className="text-[11px] mt-0.5" style={{ color: TEXT_SEC }}>{subValue}</div>}
        </div>
        {trend !== undefined && (
          <div className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium" style={{ background: `${trendColor}10`, color: trendColor }}>
            {trendUp ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      {sparkData && (
        <div className="mt-3 h-8">
          <SparklineChart data={sparkData} color={color} height={30} />
        </div>
      )}
    </div>
  );
}

/* ═══ MAIN COMPONENT ═══ */

export default function VoiceAnalytics({ token }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("7d");

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/voice-analytics/data?range=${timeRange}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        // Map sentiment icons from backend data
        if (data.sentimentData) {
          const iconMap = { "Positive": Smile, "Neutral": Meh, "Negative": Frown };
          data.sentimentData = data.sentimentData.map(s => ({
            ...s,
            icon: iconMap[s.label] || Meh,
          }));
        }
        setAnalytics(data);
        setLoading(false);
        return;
      }
    } catch { /* API unavailable */ }
    setAnalytics(emptyAnalytics());
    setLoading(false);
  }, [token, timeRange]);

  useEffect(() => { fetchAnalytics(); }, [fetchAnalytics]);

  if (loading || !analytics) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="voice-analytics-loading">
        <div className="flex items-center gap-3" style={{ color: TEXT_MUTED }}>
          <RefreshCw className="size-5 animate-spin" />
          <span className="text-sm">Loading voice analytics…</span>
        </div>
      </div>
    );
  }

  const { summary, tierBreakdown, sentimentData, personaStats, dailyVolume, costSavings, liveCalls } = analytics;

  return (
    <div className="flex-1 overflow-auto aurem-scroll" data-testid="voice-analytics">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-lg font-bold tracking-wider mb-1" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>
              VOICE AGENT ANALYTICS
            </h1>
            <p className="text-xs" style={{ color: TEXT_SEC }}>Performance metrics, sentiment analysis & ROI insights</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 p-0.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(26,48,38,0.1)' }}>
              {["24h", "7d", "30d"].map(range => (
                <button key={range} onClick={() => setTimeRange(range)} data-testid={`voice-range-${range}`}
                  className="px-3 py-1.5 text-[10px] rounded-md transition-all"
                  style={{
                    background: timeRange === range ? `${COPPER}15` : 'transparent',
                    color: timeRange === range ? COPPER : TEXT_MUTED,
                    border: timeRange === range ? `1px solid ${COPPER}30` : '1px solid transparent',
                    fontFamily: "'Montserrat', sans-serif", fontWeight: 600
                  }}
                >{range}</button>
              ))}
            </div>
            <button onClick={fetchAnalytics} data-testid="voice-refresh"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all hover:shadow-md"
              style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(26,48,38,0.1)', color: TEXT_SEC }}
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
        </div>

        {/* Live Calls Banner */}
        <div className="aurem-glass-card p-4 mb-6 flex items-center justify-between" data-testid="live-calls-banner">
          <div className="flex items-center gap-3">
            <div className="size-3 rounded-full bg-[#16a34a] animate-pulse" />
            <span className="text-sm font-semibold" style={{ color: FOREST, fontFamily: "'Montserrat', sans-serif" }}>
              {liveCalls.active} Active Calls
            </span>
            <span className="text-xs" style={{ color: TEXT_SEC }}>
              {liveCalls.queued} queued &middot; {liveCalls.avgWait}s avg wait
            </span>
          </div>
          <div className="flex items-center gap-4">
            {liveCalls.agents.map((a, i) => (
              <div key={i} className="flex items-center gap-2">
                <Radio size={12} color={a.busy ? COPPER : '#16a34a'} />
                <span className="text-[10px]" style={{ color: TEXT_SEC }}>{a.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="TOTAL CALLS" value={summary.totalCalls.toLocaleString()} subValue={`${summary.inboundCalls} in / ${summary.outboundCalls} out`} icon={PhoneCall} trend={summary.callTrend} sparkData={dailyVolume} />
          <StatCard label="AVG DURATION" value={`${summary.avgDuration}s`} subValue="Target: 180s" icon={Clock} trend={summary.durationTrend} color="#2563eb" />
          <StatCard label="ACTION RATE" value={`${summary.actionRate}%`} subValue={`${summary.actionsCompleted} completed`} icon={Zap} trend={summary.actionTrend} color="#16a34a" />
          <StatCard label="VIP CALLS" value={summary.vipCalls.toLocaleString()} subValue={`${summary.vipPercent}% of total`} icon={Award} trend={summary.vipTrend} color="#7c3aed" />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-3 gap-5 mb-6">
          {/* Tier Breakdown */}
          <div className="aurem-glass-card p-5" data-testid="tier-breakdown">
            <div className="flex items-center gap-2 mb-4">
              <PieChart size={15} color={COPPER} />
              <h3 className="text-[11px] font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>TIER BREAKDOWN</h3>
            </div>
            <DonutChart data={tierBreakdown} />
          </div>

          {/* Sentiment Analysis */}
          <div className="aurem-glass-card p-5" data-testid="sentiment-analysis">
            <div className="flex items-center gap-2 mb-4">
              <Smile size={15} color="#16a34a" />
              <h3 className="text-[11px] font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>SENTIMENT ANALYSIS</h3>
            </div>
            <div className="space-y-3">
              {sentimentData.map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${s.color}12` }}>
                    <s.icon size={16} color={s.color} />
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between mb-1">
                      <span className="text-xs" style={{ color: TEXT_SEC }}>{s.label}</span>
                      <span className="text-xs font-mono font-semibold" style={{ color: s.color }}>{s.percent}%</span>
                    </div>
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(26,48,38,0.06)' }}>
                      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${s.percent}%`, background: s.color }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 p-3 rounded-lg text-center" style={{ background: 'rgba(22,163,106,0.06)' }}>
              <span className="text-xs font-semibold" style={{ color: '#16a34a' }}>CSAT Score: {sentimentData[0].csat}/5.0</span>
            </div>
          </div>

          {/* Duration by Persona */}
          <div className="aurem-glass-card p-5" data-testid="persona-duration">
            <div className="flex items-center gap-2 mb-4">
              <BarChart2 size={15} color={COPPER} />
              <h3 className="text-[11px] font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>DURATION BY PERSONA</h3>
            </div>
            {personaStats.map((p, i) => (
              <HorizontalBar key={i} label={p.name} value={p.avgDuration} maxValue={Math.max(...personaStats.map(x => x.avgDuration))} color={p.color} />
            ))}
          </div>
        </div>

        {/* Cost Savings */}
        <div className="aurem-glass-card p-5 mb-6" data-testid="cost-savings">
          <div className="flex items-center gap-2 mb-5">
            <DollarSign size={15} color="#16a34a" />
            <h3 className="text-[11px] font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>COST SAVINGS & ROI</h3>
          </div>
          <div className="grid grid-cols-4 gap-5">
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: TEXT_MUTED, fontFamily: "'Montserrat', sans-serif" }}>AI HANDLED</div>
              <div className="text-3xl font-light font-mono" style={{ color: '#16a34a' }}>${costSavings.totalSaved.toLocaleString()}</div>
              <div className="text-xs mt-1" style={{ color: TEXT_SEC }}>saved vs human agents</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: TEXT_MUTED, fontFamily: "'Montserrat', sans-serif" }}>AI COST/CALL</div>
              <div className="text-2xl font-light font-mono" style={{ color: FOREST }}>${costSavings.aiCostPerCall}</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: TEXT_MUTED, fontFamily: "'Montserrat', sans-serif" }}>HUMAN COST/CALL</div>
              <div className="text-2xl font-light font-mono" style={{ color: TEXT_SEC }}>${costSavings.humanCostPerCall}</div>
            </div>
            <div className="flex items-center justify-center">
              <div className="px-5 py-3 rounded-xl text-center" style={{ background: 'rgba(22,163,106,0.08)', border: '1px solid rgba(22,163,106,0.15)' }}>
                <div className="text-2xl font-bold" style={{ color: '#16a34a', fontFamily: "'Montserrat', sans-serif" }}>{costSavings.savingsPercent}%</div>
                <div className="text-[10px]" style={{ color: TEXT_SEC }}>cost reduction</div>
              </div>
            </div>
          </div>
        </div>

        {/* Action Conversion Funnel */}
        <div className="aurem-glass-card p-5" data-testid="conversion-funnel">
          <div className="flex items-center gap-2 mb-6">
            <Target size={15} color={COPPER} />
            <h3 className="text-[11px] font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: FOREST }}>ACTION CONVERSION FUNNEL</h3>
          </div>
          <div className="flex items-center justify-between">
            {[
              { label: "Total Calls", value: summary.totalCalls, color: COPPER },
              { label: "Intent Detected", value: Math.round(summary.totalCalls * 0.85), color: "#2563eb" },
              { label: "Action Attempted", value: Math.round(summary.totalCalls * 0.45), color: "#7c3aed" },
              { label: "Action Completed", value: summary.actionsCompleted, color: "#16a34a" }
            ].map((stage, i, arr) => (
              <div key={i} className="flex-1 text-center relative">
                {i < arr.length - 1 && (
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-full h-0.5"
                    style={{ background: `linear-gradient(90deg, ${stage.color}30, ${arr[i+1].color}30)` }} />
                )}
                <div className="size-16 rounded-full flex items-center justify-center mx-auto relative z-10"
                  style={{ background: `${stage.color}10`, border: `2px solid ${stage.color}`, boxShadow: `0 0 15px ${stage.color}10` }}>
                  <span className="text-lg font-semibold" style={{ color: stage.color }}>{stage.value}</span>
                </div>
                <div className="text-[10px] mt-2" style={{ color: TEXT_SEC }}>{stage.label}</div>
                {i > 0 && (
                  <div className="text-[9px] mt-0.5" style={{ color: TEXT_MUTED }}>
                    {Math.round((stage.value / arr[i-1].value) * 100)}% conv.
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══ EMPTY STATE DATA ═══ */

function emptyAnalytics() {
  return {
    summary: {
      totalCalls: 0, inboundCalls: 0, outboundCalls: 0,
      avgDuration: 0, actionRate: 0, actionsCompleted: 0,
      vipCalls: 0, vipPercent: 0,
      callTrend: 0, durationTrend: 0, actionTrend: 0, vipTrend: 0
    },
    tierBreakdown: [
      { label: "Standard", value: 0, color: "#2563eb" },
      { label: "Premium", value: 0, color: "#7c3aed" },
      { label: "VIP", value: 0, color: COPPER },
      { label: "Enterprise", value: 0, color: "#16a34a" }
    ],
    sentimentData: [
      { label: "Positive", percent: 0, color: "#16a34a", icon: Smile, csat: 0 },
      { label: "Neutral", percent: 0, color: "#d97706", icon: Meh, csat: 0 },
      { label: "Negative", percent: 0, color: "#dc2626", icon: Frown, csat: 0 }
    ],
    personaStats: [],
    dailyVolume: [0, 0, 0, 0, 0, 0, 0],
    costSavings: {
      totalSaved: 0, aiCostPerCall: 0, humanCostPerCall: 0, savingsPercent: 0
    },
    liveCalls: {
      active: 0, queued: 0, avgWait: 0,
      agents: []
    }
  };
}
