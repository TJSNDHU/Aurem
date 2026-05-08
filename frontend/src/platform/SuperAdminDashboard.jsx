/**
 * AUREM Super Admin Dashboard
 * All tenants, MRR tracking, usage overview, churn alerts, manual plan overrides
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, DollarSign, TrendingUp, AlertTriangle, ArrowUpRight,
  RefreshCw, Shield, Activity, ChevronDown, Check, X, Search
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const PLAN_COLORS = { trial: '#888', starter: '#D4AF37', growth: '#8B5CF6', enterprise: '#FF6B00' };

export default function SuperAdminDashboard({ token }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [overrideTarget, setOverrideTarget] = useState(null);
  const [overridePlan, setOverridePlan] = useState('');
  const [search, setSearch] = useState('');

  const fetchTenants = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/admin/tenants`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchTenants(); }, [fetchTenants]);

  const handleOverride = async () => {
    if (!overrideTarget || !overridePlan) return;
    try {
      await fetch(`${API_URL}/api/admin/tenants/plan`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_id: overrideTarget, plan: overridePlan }),
      });
      setOverrideTarget(null);
      fetchTenants();
    } catch (err) { console.error(err); }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="admin-loading">
        <RefreshCw className="w-5 h-5 animate-spin text-[#888]" />
      </div>
    );
  }

  const tenants = data?.tenants || [];
  const filtered = tenants.filter(t => {
    if (filter === 'churn' && !t.churn_risk) return false;
    if (filter === 'upsell' && !t.upsell_trigger) return false;
    if (filter === 'active' && t.status !== 'active') return false;
    if (search && !t.business_id.includes(search) && !t.email?.includes(search)) return false;
    return true;
  });

  return (
    <div className="flex-1 overflow-auto" data-testid="super-admin-dashboard">
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-xl font-semibold text-[#FF6B00] tracking-wider mb-1">Super Admin</h1>
        <p className="text-xs text-[#888] mb-6">Tenant management, MRR tracking, churn alerts</p>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            { label: 'Total MRR', value: `$${data?.total_mrr?.toLocaleString() || 0}`, icon: DollarSign, color: '#4ade80' },
            { label: 'Active Tenants', value: data?.active_tenants || 0, icon: Users, color: '#8B5CF6' },
            { label: 'Churn Risk', value: data?.churn_risk_count || 0, icon: AlertTriangle, color: '#ef4444' },
            { label: 'Upsell Ready', value: data?.upsell_count || 0, icon: ArrowUpRight, color: '#FF6B00' },
          ].map((kpi, i) => (
            <div key={i} className="p-4 border border-white/5 rounded-xl" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <div className="flex items-center gap-2 mb-2">
                <kpi.icon className="w-4 h-4" style={{ color: kpi.color }} />
                <span className="text-[10px] text-[#888] uppercase tracking-wider">{kpi.label}</span>
              </div>
              <span className="text-2xl font-bold text-white">{kpi.value}</span>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-4">
          {['all', 'active', 'churn', 'upsell'].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              data-testid={`filter-${f}`}
              className={`px-3 py-1.5 text-[10px] font-medium rounded-lg transition-all ${
                filter === f ? 'bg-[#FF6B00]/20 text-[#FF6B00]' : 'text-[#666] hover:text-white'
              }`}>{f === 'all' ? 'All' : f === 'churn' ? 'Churn Risk' : f === 'upsell' ? 'Upsell' : 'Active'}</button>
          ))}
          <div className="ml-auto relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#666]" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tenants..."
              className="pl-8 pr-3 py-1.5 text-[10px] bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-[#555] focus:outline-none focus:border-[#FF6B00]/30 w-48" />
          </div>
        </div>

        {/* Tenants Table */}
        <div className="border border-white/5 rounded-xl overflow-hidden" style={{ background: 'rgba(255,255,255,0.02)' }}>
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                {['Tenant', 'Plan', 'MRR', 'Usage', 'Status', 'Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-[10px] text-[#888] font-medium text-left uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filtered.map(t => (
                <tr key={t.business_id} className="hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <div className="text-xs text-white font-medium">{t.business_id}</div>
                    <div className="text-[10px] text-[#666]">{t.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 text-[9px] font-bold rounded-full uppercase tracking-wider"
                      style={{ color: PLAN_COLORS[t.plan] || '#888', background: (PLAN_COLORS[t.plan] || '#888') + '15' }}>
                      {t.plan_label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-white font-medium">${t.mrr}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${Math.min(t.usage_percent, 100)}%`,
                          background: t.usage_percent >= 90 ? '#ef4444' : t.usage_percent >= 70 ? '#f59e0b' : '#4ade80',
                        }} />
                      </div>
                      <span className="text-[10px] text-[#888]">{t.actions_used}/{t.actions_limit === -1 ? '∞' : t.actions_limit}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {t.churn_risk && <span className="px-1.5 py-0.5 text-[8px] font-bold bg-red-500/10 text-red-400 rounded">CHURN</span>}
                      {t.upsell_trigger && <span className="px-1.5 py-0.5 text-[8px] font-bold bg-[#FF6B00]/10 text-[#FF6B00] rounded">UPSELL</span>}
                      {!t.churn_risk && !t.upsell_trigger && <span className="text-[10px] text-[#4ade80]">{t.status}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => { setOverrideTarget(t.business_id); setOverridePlan(t.plan); }}
                      data-testid={`override-${t.business_id}`}
                      className="text-[10px] text-[#FF6B00] hover:underline">Override Plan</button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-xs text-[#666]">No tenants found</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Override Modal */}
        {overrideTarget && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="override-modal">
            <div className="w-80 p-5 rounded-xl border border-white/10" style={{ background: '#1A1A2E' }}>
              <h3 className="text-sm font-semibold text-white mb-1">Override Plan</h3>
              <p className="text-[10px] text-[#888] mb-4">Tenant: {overrideTarget}</p>
              <select value={overridePlan} onChange={e => setOverridePlan(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-white/5 border border-white/10 rounded-lg text-white mb-4 focus:outline-none">
                {['trial', 'starter', 'growth', 'enterprise'].map(p => (
                  <option key={p} value={p} className="bg-[#1A1A2E]">{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                ))}
              </select>
              <div className="flex gap-2">
                <button onClick={handleOverride} data-testid="confirm-override"
                  className="flex-1 py-2 text-xs font-medium text-[#1A3026] rounded-lg" style={{ background: 'linear-gradient(135deg, #FF6B00, #CC5500)' }}>
                  Confirm
                </button>
                <button onClick={() => setOverrideTarget(null)}
                  className="flex-1 py-2 text-xs font-medium text-[#888] border border-white/10 rounded-lg hover:text-white">
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
