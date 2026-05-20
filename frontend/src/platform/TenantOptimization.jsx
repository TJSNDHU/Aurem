import React, { useState, useEffect, useCallback , useMemo } from 'react';
import { Shield, TrendingUp, Zap, AlertTriangle, CheckCircle, XCircle, Play, Pause, RotateCcw, ChevronRight, Activity, BarChart3, RefreshCw } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const STAGE_ORDER = ['profiled', 'shadow', '10%', '25%', '50%', '100%', 'monitoring'];
const STAGE_COLORS = {
  'not_started': '#555',
  'profiled': '#6B7280',
  'shadow': '#8B5CF6',
  '10%': '#3B82F6',
  '25%': '#0EA5E9',
  '50%': '#10B981',
  '100%': '#22C55E',
  'monitoring': '#FF6B00',
  'paused': '#EAB308',
  'rolled_back': '#EF4444',
  'blocked': '#DC2626',
};

const RISK_COLORS = { GREEN: '#22C55E', YELLOW: '#EAB308', RED: '#EF4444' };

function TenantOptimization({ token }) {
  const [dashboard, setDashboard] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [tenantMetrics, setTenantMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [modules, setModules] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [dashRes, profRes, modRes] = await Promise.all([
        fetch(`${API}/api/optimization/dashboard`, { headers }),
        fetch(`${API}/api/optimization/profiles`, { headers }),
        fetch(`${API}/api/system/modules`, { headers }),
      ]);
      if (dashRes.ok) setDashboard(await dashRes.json());
      if (profRes.ok) {
        const d = await profRes.json();
        setProfiles(d.profiles || []);
      }
      if (modRes.ok) setModules(await modRes.json());
    } catch (e) {
      console.error('Fetch error:', e);
    }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const fetchMetrics = async (tenantId) => {
    setSelectedTenant(tenantId);
    setTenantMetrics(null);
    try {
      const res = await fetch(`${API}/api/optimization/metrics/${tenantId}?days=30`, { headers });
      if (res.ok) setTenantMetrics(await res.json());
    } catch (e) { console.error(e); }
  };

  const profileTenant = async (tenantId) => {
    setActionLoading(tenantId);
    try {
      await fetch(`${API}/api/optimization/profile/${tenantId}`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const profileAll = async () => {
    setActionLoading('all');
    try {
      await fetch(`${API}/api/optimization/profile-all`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const toggleOptimization = async (tenantId, enabled) => {
    setActionLoading(tenantId);
    try {
      await fetch(`${API}/api/optimization/toggle/${tenantId}`, {
        method: 'POST', headers, body: JSON.stringify({ enabled }),
      });
      await fetchData();
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const forceRollback = async (tenantId) => {
    setActionLoading(tenantId);
    try {
      await fetch(`${API}/api/optimization/rollback/${tenantId}`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  const advanceStage = async (tenantId) => {
    setActionLoading(tenantId);
    try {
      await fetch(`${API}/api/optimization/advance-stage/${tenantId}`, { method: 'POST', headers });
      await fetchData();
    } catch (e) { console.error(e); }
    setActionLoading(null);
  };

  if (loading) {
    return (
      <div data-testid="tenant-optimization-loading" className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full size-8 border-2 border-[#FF6B00] border-t-transparent" />
      </div>
    );
  }

  return (
    <div data-testid="tenant-optimization-dashboard" className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#F0EBE0]" data-testid="optimization-title">
            Tenant Optimization
          </h1>
          <p className="text-sm text-[#8B8578] mt-1">
            Safe deployment pipeline for token reduction across customer tenants
          </p>
        </div>
        <div className="flex gap-2">
          <button
            data-testid="refresh-btn"
            onClick={fetchData}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a1f] border border-[#2a2a30] text-[#8B8578] hover:text-[#FF6B00] text-xs flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw className="size-3.5" /> Refresh
          </button>
          <button
            data-testid="profile-all-btn"
            onClick={profileAll}
            disabled={actionLoading === 'all'}
            className="px-3 py-1.5 rounded-lg bg-[#FF6B00]/10 border border-[#FF6B00]/30 text-[#FF6B00] hover:bg-[#FF6B00]/20 text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
          >
            {actionLoading === 'all' ? <RefreshCw className="size-3.5 animate-spin" /> : <Zap className="size-3.5" />}
            Profile All Tenants
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3" data-testid="summary-cards">
        <SummaryCard
          label="Tenants Profiled"
          value={dashboard?.total_tenants_profiled || 0}
          icon={<Activity className="size-4" />}
          color="#FF6B00"
        />
        <SummaryCard
          label="Fully Optimized"
          value={dashboard?.tenants_fully_optimized || 0}
          icon={<CheckCircle className="size-4" />}
          color="#22C55E"
        />
        <SummaryCard
          label="In Shadow Mode"
          value={dashboard?.tenants_in_shadow || 0}
          icon={<Shield className="size-4" />}
          color="#8B5CF6"
        />
        <SummaryCard
          label="Blocked"
          value={dashboard?.tenants_blocked || 0}
          icon={<XCircle className="size-4" />}
          color="#EF4444"
        />
        <SummaryCard
          label="Tokens Saved"
          value={formatNumber(dashboard?.total_tokens_saved_estimate || 0)}
          subtitle={`~$${dashboard?.total_cost_saved_estimate || 0}`}
          icon={<TrendingUp className="size-4" />}
          color="#10B981"
        />
      </div>

      {/* Risk Distribution */}
      {dashboard?.risk_distribution && (
        <div className="rounded-xl bg-[#0f0f12] border border-[#1e1e24] p-4" data-testid="risk-distribution">
          <h3 className="text-xs font-semibold text-[#8B8578] uppercase tracking-wider mb-3">Risk Distribution</h3>
          <div className="flex gap-4">
            {Object.entries(dashboard.risk_distribution).map(([level, count]) => (
              <div key={level} className="flex items-center gap-2">
                <div className="size-3 rounded-full" style={{ background: RISK_COLORS[level] }} />
                <span className="text-sm text-[#F0EBE0] font-medium">{count}</span>
                <span className="text-xs text-[#8B8578]">{level}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tenant Profiles Table */}
      <div className="rounded-xl bg-[#0f0f12] border border-[#1e1e24] overflow-hidden" data-testid="profiles-table">
        <div className="px-4 py-3 border-b border-[#1e1e24]">
          <h3 className="text-sm font-semibold text-[#F0EBE0]">Tenant Profiles</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#1e1e24] text-[#8B8578]">
                <th className="px-4 py-2.5 text-left font-medium">Tenant</th>
                <th className="px-4 py-2.5 text-left font-medium">Risk</th>
                <th className="px-4 py-2.5 text-left font-medium">Stage</th>
                <th className="px-4 py-2.5 text-right font-medium">Tokens/Call</th>
                <th className="px-4 py-2.5 text-right font-medium">Cache Rate</th>
                <th className="px-4 py-2.5 text-right font-medium">Calls (7d)</th>
                <th className="px-4 py-2.5 text-left font-medium">Status</th>
                <th className="px-4 py-2.5 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {profiles.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-[#5C5548]">
                    No tenants profiled yet. Click "Profile All Tenants" to begin.
                  </td>
                </tr>
              ) : (
                profiles.map((p) => (
                  <tr
                    key={p.tenant_id}
                    data-testid={`tenant-row-${p.tenant_id}`}
                    className={`border-b border-[#1e1e24]/50 hover:bg-[#1a1a1f] cursor-pointer transition-colors ${
                      selectedTenant === p.tenant_id ? 'bg-[#1a1a1f]' : ''
                    }`}
                    onClick={() => fetchMetrics(p.tenant_id)}
                  >
                    <td className="px-4 py-2.5 text-[#F0EBE0] font-medium">{p.tenant_id}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold"
                        style={{
                          background: `${RISK_COLORS[p.risk_classification]}15`,
                          color: RISK_COLORS[p.risk_classification],
                          border: `1px solid ${RISK_COLORS[p.risk_classification]}30`,
                        }}
                      >
                        {p.risk_score}/10 {p.risk_classification}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className="inline-block px-2 py-0.5 rounded text-[10px] font-medium"
                        style={{
                          background: `${STAGE_COLORS[p.optimization_stage] || '#555'}20`,
                          color: STAGE_COLORS[p.optimization_stage] || '#888',
                        }}
                      >
                        {p.optimization_stage || 'not_started'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-[#F0EBE0] font-mono">{p.avg_tokens_per_call}</td>
                    <td className="px-4 py-2.5 text-right text-[#FF6B00] font-mono">{p.cache_candidate_rate}%</td>
                    <td className="px-4 py-2.5 text-right text-[#8B8578] font-mono">{p.total_calls_7d}</td>
                    <td className="px-4 py-2.5">
                      {p.optimization_enabled ? (
                        <span className="text-[#22C55E] flex items-center gap-1"><CheckCircle className="size-3" /> Active</span>
                      ) : (
                        <span className="text-[#8B8578] flex items-center gap-1"><Pause className="size-3" /> Inactive</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center gap-1 justify-end" onClick={(e) => e.stopPropagation()}>
                        {p.optimization_enabled ? (
                          <button
                            data-testid={`pause-${p.tenant_id}`}
                            onClick={() => toggleOptimization(p.tenant_id, false)}
                            disabled={actionLoading === p.tenant_id}
                            className="p-1 rounded hover:bg-[#EAB308]/10 text-[#EAB308] transition-colors"
                            title="Pause Optimization"
                          >
                            <Pause className="size-3.5" />
                          </button>
                        ) : (
                          <button
                            data-testid={`enable-${p.tenant_id}`}
                            onClick={() => toggleOptimization(p.tenant_id, true)}
                            disabled={actionLoading === p.tenant_id}
                            className="p-1 rounded hover:bg-[#22C55E]/10 text-[#22C55E] transition-colors"
                            title="Enable Optimization"
                          >
                            <Play className="size-3.5" />
                          </button>
                        )}
                        <button
                          data-testid={`rollback-${p.tenant_id}`}
                          onClick={() => forceRollback(p.tenant_id)}
                          disabled={actionLoading === p.tenant_id}
                          className="p-1 rounded hover:bg-[#EF4444]/10 text-[#EF4444] transition-colors"
                          title="Force Rollback"
                        >
                          <RotateCcw className="size-3.5" />
                        </button>
                        <button
                          data-testid={`advance-${p.tenant_id}`}
                          onClick={() => advanceStage(p.tenant_id)}
                          disabled={actionLoading === p.tenant_id}
                          className="p-1 rounded hover:bg-[#FF6B00]/10 text-[#FF6B00] transition-colors"
                          title="Advance Stage"
                        >
                          <ChevronRight className="size-3.5" />
                        </button>
                        <button
                          data-testid={`reprofile-${p.tenant_id}`}
                          onClick={() => profileTenant(p.tenant_id)}
                          disabled={actionLoading === p.tenant_id}
                          className="p-1 rounded hover:bg-[#3B82F6]/10 text-[#3B82F6] transition-colors"
                          title="Re-Profile"
                        >
                          <RefreshCw className={`size-3.5 ${actionLoading === p.tenant_id ? 'animate-spin' : ''}`} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Tenant Detail Panel */}
      {selectedTenant && tenantMetrics && (
        <div className="rounded-xl bg-[#0f0f12] border border-[#FF6B00]/20 p-5" data-testid="tenant-detail-panel">
          <h3 className="text-sm font-semibold text-[#FF6B00] mb-4">
            Metrics: {selectedTenant} (Last 30 Days)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Cache Hit Rate" value={`${tenantMetrics.cache_hit_rate}%`} target="30%" good={tenantMetrics.cache_hit_rate >= 30} />
            <MetricCard label="Token Savings" value={`${tenantMetrics.tokens_saved_pct}%`} target=">20%" good={tenantMetrics.tokens_saved_pct >= 20} />
            <MetricCard label="Error Rate" value={`${tenantMetrics.error_rate}%`} target="<0.5%" good={tenantMetrics.error_rate < 0.5} />
            <MetricCard label="Est. Cost Saved" value={`$${tenantMetrics.estimated_cost_saved}`} good={tenantMetrics.estimated_cost_saved > 0} />
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3">
            <div className="text-center p-2 rounded-lg bg-[#1a1a1f]">
              <div className="text-lg font-bold text-[#F0EBE0] font-mono">{tenantMetrics.total_calls}</div>
              <div className="text-[10px] text-[#8B8578]">Total Calls</div>
            </div>
            <div className="text-center p-2 rounded-lg bg-[#1a1a1f]">
              <div className="text-lg font-bold text-[#F0EBE0] font-mono">{tenantMetrics.cached_calls}</div>
              <div className="text-[10px] text-[#8B8578]">Cached Calls</div>
            </div>
            <div className="text-center p-2 rounded-lg bg-[#1a1a1f]">
              <div className="text-lg font-bold text-[#F0EBE0] font-mono">{formatNumber(tenantMetrics.tokens_saved_total)}</div>
              <div className="text-[10px] text-[#8B8578]">Tokens Saved</div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[10px] text-[#8B8578]">Health:</span>
            <span className={`text-xs font-medium ${
              tenantMetrics.health === 'healthy' ? 'text-[#22C55E]' :
              tenantMetrics.health === 'degraded' ? 'text-[#EAB308]' : 'text-[#EF4444]'
            }`}>
              {tenantMetrics.health?.toUpperCase()}
            </span>
          </div>
        </div>
      )}

      {/* System Modules Health */}
      {modules && (
        <div className="rounded-xl bg-[#0f0f12] border border-[#1e1e24] p-4" data-testid="modules-health">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-[#8B8578] uppercase tracking-wider">System Modules</h3>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
              modules.summary?.health === 'healthy' ? 'bg-[#22C55E]/10 text-[#22C55E]' :
              modules.summary?.health === 'degraded' ? 'bg-[#EAB308]/10 text-[#EAB308]' :
              'bg-[#EF4444]/10 text-[#EF4444]'
            }`}>
              {modules.summary?.loaded}/{modules.summary?.total} loaded
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(modules.modules || {}).map(([section, mods]) => (
              <div key={section} className="rounded-lg bg-[#1a1a1f] p-3">
                <h4 className="text-[10px] uppercase text-[#FF6B00] font-semibold tracking-wider mb-2">
                  {section.replace(/_/g, ' ')}
                </h4>
                <div className="space-y-1">
                  {Object.entries(mods).map(([name, info]) => (
                    <div key={name} className="flex items-center justify-between text-[11px]">
                      <span className="text-[#F0EBE0]">{name}</span>
                      <span className={
                        info.status === 'loaded' ? 'text-[#22C55E]' :
                        info.status === 'partial' ? 'text-[#EAB308]' : 'text-[#EF4444]'
                      }>
                        {info.status === 'loaded' ? '●' : info.status === 'partial' ? '◐' : '○'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, subtitle, icon, color }) {
  return (
    <div className="rounded-xl bg-[#0f0f12] border border-[#1e1e24] p-3" data-testid={`summary-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-center gap-2 mb-1.5">
        <div className="p-1 rounded" style={{ background: `${color}15`, color }}>{icon}</div>
        <span className="text-[10px] text-[#8B8578] uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-xl font-bold font-mono" style={{ color }}>{value}</div>
      {subtitle && <div className="text-[10px] text-[#5C5548] mt-0.5">{subtitle}</div>}
    </div>
  );
}

function MetricCard({ label, value, target, good }) {
  return (
    <div className={`rounded-lg p-3 border ${good ? 'bg-[#22C55E]/5 border-[#22C55E]/20' : 'bg-[#EF4444]/5 border-[#EF4444]/20'}`}>
      <div className="text-[10px] text-[#8B8578]">{label}</div>
      <div className={`text-lg font-bold font-mono ${good ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>{value}</div>
      {target && <div className="text-[9px] text-[#5C5548]">Target: {target}</div>}
    </div>
  );
}

function formatNumber(n) {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

export default TenantOptimization;
