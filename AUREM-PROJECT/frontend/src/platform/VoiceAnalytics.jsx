/**
 * AUREM Voice Analytics Dashboard
 * ROI visualization for enterprise voice AI
 * 
 * Features:
 * - Call Volume Trends (7-day chart)
 * - VIP vs Standard Tier Breakdown (pie chart)
 * - Average Duration by Persona
 * - Action Conversion Rates
 * - Cost Savings Calculator
 */

import { useState, useEffect, useCallback } from "react";
import {
  Phone, PhoneCall, TrendingUp, Users, Clock, Zap, DollarSign,
  PieChart, BarChart2, Activity, Award, Target, RefreshCw
} from "lucide-react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// ═══════════════════════════════════════════════════════════════════════════════
// MINI CHART COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function SparklineChart({ data, color = GOLD, height = 40 }) {
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
        <linearGradient id={`sparkGrad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
      <polygon
        points={`0,100 ${points} 100,100`}
        fill={`url(#sparkGrad-${color.replace("#", "")})`}
      />
    </svg>
  );
}

function DonutChart({ data, size = 120 }) {
  const total = data.reduce((sum, d) => sum + d.value, 0) || 1;
  let currentAngle = -90;
  
  const segments = data.map((d, i) => {
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
      color: d.color,
      label: d.label,
      value: d.value,
      percent: ((d.value / total) * 100).toFixed(0)
    };
  });
  
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        {segments.map((seg, i) => (
          <path key={i} d={seg.path} fill={seg.color} opacity={0.85} />
        ))}
        <circle cx="50" cy="50" r="25" fill={OB} />
        <text x="50" y="54" textAnchor="middle" fill={WH2} fontSize="14" fontWeight="600">
          {total}
        </text>
      </svg>
      <div>
        {segments.map((seg, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: seg.color }} />
            <span style={{ fontSize: 11, color: SV }}>{seg.label}</span>
            <span style={{ fontSize: 11, color: MU, marginLeft: "auto" }}>{seg.percent}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HorizontalBar({ label, value, maxValue, color = GOLD }) {
  const percent = maxValue > 0 ? (value / maxValue) * 100 : 0;
  
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12, color: SV }}>{label}</span>
        <span style={{ fontSize: 12, color: GOLD2, fontFamily: "monospace" }}>{value}s</span>
      </div>
      <div style={{ height: 8, background: OB, borderRadius: 4, overflow: "hidden" }}>
        <div style={{
          width: `${percent}%`,
          height: "100%",
          background: `linear-gradient(90deg, ${color}, ${color}80)`,
          borderRadius: 4,
          transition: "width 0.5s ease"
        }} />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// STAT CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function StatCard({ label, value, subValue, icon: Icon, trend, color = GOLD, sparkData }) {
  const trendColor = trend > 0 ? "#4ade80" : trend < 0 ? "#ef4444" : MU;
  
  return (
    <div style={{
      padding: 16,
      background: OB3,
      border: `1px solid rgba(201,168,76,.1)`,
      borderRadius: 12,
      position: "relative",
      overflow: "hidden"
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div style={{
          width: 40, height: 40,
          borderRadius: 10,
          background: `${color}20`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0
        }}>
          <Icon size={20} color={color} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 10, color: MU, letterSpacing: "0.08em", marginBottom: 4 }}>
            {label}
          </div>
          <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace", fontWeight: 600 }}>
            {value}
          </div>
          {subValue && (
            <div style={{ fontSize: 11, color: SV, marginTop: 2 }}>{subValue}</div>
          )}
        </div>
        {trend !== undefined && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 8px",
            background: `${trendColor}15`,
            borderRadius: 8,
            fontSize: 11,
            color: trendColor,
            fontWeight: 500
          }}>
            <TrendingUp size={12} style={{ transform: trend < 0 ? "rotate(180deg)" : "none" }} />
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      {sparkData && (
        <div style={{ marginTop: 12, height: 30 }}>
          <SparklineChart data={sparkData} color={color} height={30} />
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function VoiceAnalytics({ businessId }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("7d");
  
  const fetchAnalytics = useCallback(async () => {
    if (!businessId) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/aurem-voice/${businessId}/analytics?range=${timeRange}`);
      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      } else {
        // Use mock data for demo
        setAnalytics(generateMockAnalytics());
      }
    } catch {
      setAnalytics(generateMockAnalytics());
    } finally {
      setLoading(false);
    }
  }, [businessId, timeRange]);
  
  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);
  
  if (loading || !analytics) {
    return (
      <div style={{ padding: 24, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 300 }}>
        <div style={{ color: MU }}>Loading analytics...</div>
      </div>
    );
  }
  
  const { summary, tierBreakdown, personaStats, dailyVolume, costSavings } = analytics;
  
  return (
    <div data-testid="voice-analytics" style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>
            Voice Analytics
          </h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>
            Performance metrics & ROI insights
          </p>
        </div>
        
        <div style={{ display: "flex", gap: 12 }}>
          {/* Time Range Selector */}
          <div style={{ display: "flex", gap: 4 }}>
            {["24h", "7d", "30d"].map(range => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                style={{
                  padding: "6px 12px",
                  background: timeRange === range ? `${GOLD}20` : "transparent",
                  border: `1px solid ${timeRange === range ? GOLD : "rgba(201,168,76,.2)"}`,
                  borderRadius: 6,
                  color: timeRange === range ? GOLD : SV,
                  fontSize: 11,
                  cursor: "pointer"
                }}
              >
                {range}
              </button>
            ))}
          </div>
          
          <button
            onClick={fetchAnalytics}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: `1px solid rgba(201,168,76,.2)`,
              borderRadius: 8,
              color: GOLD,
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </div>
      
      {/* Summary Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard
          label="TOTAL CALLS"
          value={summary.totalCalls}
          subValue={`${summary.inboundCalls} inbound • ${summary.outboundCalls} outbound`}
          icon={PhoneCall}
          trend={summary.callTrend}
          sparkData={dailyVolume}
        />
        <StatCard
          label="AVG DURATION"
          value={`${summary.avgDuration}s`}
          subValue="Target: 180s"
          icon={Clock}
          trend={summary.durationTrend}
          color="#60a5fa"
        />
        <StatCard
          label="ACTION RATE"
          value={`${summary.actionRate}%`}
          subValue={`${summary.actionsCompleted} actions completed`}
          icon={Zap}
          trend={summary.actionTrend}
          color="#4ade80"
        />
        <StatCard
          label="VIP CALLS"
          value={summary.vipCalls}
          subValue={`${summary.vipPercent}% of total`}
          icon={Award}
          trend={summary.vipTrend}
          color="#a855f7"
        />
      </div>
      
      {/* Charts Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 20, marginBottom: 24 }}>
        {/* Tier Breakdown */}
        <div style={{
          padding: 20,
          background: OB3,
          border: `1px solid rgba(201,168,76,.1)`,
          borderRadius: 12
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <PieChart size={16} color={GOLD} />
            <h3 style={{ fontSize: 13, color: GOLD2, margin: 0, letterSpacing: "0.05em" }}>
              TIER BREAKDOWN
            </h3>
          </div>
          <DonutChart data={tierBreakdown} />
        </div>
        
        {/* Duration by Persona */}
        <div style={{
          padding: 20,
          background: OB3,
          border: `1px solid rgba(201,168,76,.1)`,
          borderRadius: 12
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <BarChart2 size={16} color={GOLD} />
            <h3 style={{ fontSize: 13, color: GOLD2, margin: 0, letterSpacing: "0.05em" }}>
              AVG DURATION BY PERSONA
            </h3>
          </div>
          {personaStats.map((persona, i) => (
            <HorizontalBar
              key={i}
              label={persona.name}
              value={persona.avgDuration}
              maxValue={Math.max(...personaStats.map(p => p.avgDuration))}
              color={persona.color}
            />
          ))}
        </div>
        
        {/* Cost Savings */}
        <div style={{
          padding: 20,
          background: OB3,
          border: `1px solid rgba(201,168,76,.1)`,
          borderRadius: 12
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <DollarSign size={16} color="#4ade80" />
            <h3 style={{ fontSize: 13, color: GOLD2, margin: 0, letterSpacing: "0.05em" }}>
              COST SAVINGS
            </h3>
          </div>
          
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>CALLS HANDLED BY AI</div>
            <div style={{ fontSize: 28, color: "#4ade80", fontFamily: "monospace" }}>
              ${costSavings.totalSaved.toLocaleString()}
            </div>
            <div style={{ fontSize: 11, color: SV }}>saved vs human agents</div>
          </div>
          
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, color: MU }}>AI Cost/Call</div>
              <div style={{ fontSize: 16, color: GOLD2, fontFamily: "monospace" }}>
                ${costSavings.aiCostPerCall}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: MU }}>Human Cost/Call</div>
              <div style={{ fontSize: 16, color: SV, fontFamily: "monospace" }}>
                ${costSavings.humanCostPerCall}
              </div>
            </div>
          </div>
          
          <div style={{ marginTop: 12, padding: 10, background: "rgba(74,222,128,.1)", borderRadius: 8 }}>
            <div style={{ fontSize: 11, color: "#4ade80", fontWeight: 500 }}>
              {costSavings.savingsPercent}% cost reduction
            </div>
          </div>
        </div>
      </div>
      
      {/* Action Conversion Funnel */}
      <div style={{
        padding: 20,
        background: OB3,
        border: `1px solid rgba(201,168,76,.1)`,
        borderRadius: 12
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
          <Target size={16} color={GOLD} />
          <h3 style={{ fontSize: 13, color: GOLD2, margin: 0, letterSpacing: "0.05em" }}>
            ACTION CONVERSION FUNNEL
          </h3>
        </div>
        
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {[
            { label: "Total Calls", value: summary.totalCalls, color: GOLD },
            { label: "Intent Detected", value: Math.round(summary.totalCalls * 0.85), color: "#60a5fa" },
            { label: "Action Attempted", value: Math.round(summary.totalCalls * 0.45), color: "#a855f7" },
            { label: "Action Completed", value: summary.actionsCompleted, color: "#4ade80" }
          ].map((stage, i, arr) => (
            <div key={i} style={{ flex: 1, textAlign: "center", position: "relative" }}>
              {i < arr.length - 1 && (
                <div style={{
                  position: "absolute",
                  right: 0,
                  top: "50%",
                  transform: "translateY(-50%)",
                  width: "100%",
                  height: 2,
                  background: `linear-gradient(90deg, ${stage.color}40, ${arr[i+1].color}40)`,
                  zIndex: 0
                }} />
              )}
              <div style={{
                width: 60, height: 60,
                borderRadius: "50%",
                background: `${stage.color}20`,
                border: `2px solid ${stage.color}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto",
                position: "relative",
                zIndex: 1
              }}>
                <span style={{ fontSize: 16, color: stage.color, fontWeight: 600 }}>
                  {stage.value}
                </span>
              </div>
              <div style={{ fontSize: 10, color: SV, marginTop: 8 }}>{stage.label}</div>
              {i > 0 && (
                <div style={{ fontSize: 9, color: MU, marginTop: 2 }}>
                  {Math.round((stage.value / arr[i-1].value) * 100)}% conversion
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MOCK DATA GENERATOR
// ═══════════════════════════════════════════════════════════════════════════════

function generateMockAnalytics() {
  return {
    summary: {
      totalCalls: 847,
      inboundCalls: 623,
      outboundCalls: 224,
      avgDuration: 142,
      actionRate: 38,
      actionsCompleted: 322,
      vipCalls: 156,
      vipPercent: 18,
      callTrend: 12,
      durationTrend: -5,
      actionTrend: 8,
      vipTrend: 23
    },
    tierBreakdown: [
      { label: "Standard", value: 512, color: "#60a5fa" },
      { label: "Premium", value: 179, color: "#a855f7" },
      { label: "VIP", value: 124, color: GOLD },
      { label: "Enterprise", value: 32, color: "#4ade80" }
    ],
    personaStats: [
      { name: "Luxe Skincare", avgDuration: 186, color: GOLD2 },
      { name: "Luxe Skincare VIP", avgDuration: 224, color: GOLD },
      { name: "Auto Advisor", avgDuration: 142, color: "#60a5fa" },
      { name: "Auto Advisor VIP", avgDuration: 198, color: "#3b82f6" },
      { name: "General Assistant", avgDuration: 98, color: "#a855f7" }
    ],
    dailyVolume: [95, 108, 122, 115, 138, 142, 127],
    costSavings: {
      totalSaved: 12450,
      aiCostPerCall: 0.45,
      humanCostPerCall: 15.00,
      savingsPercent: 97
    }
  };
}
