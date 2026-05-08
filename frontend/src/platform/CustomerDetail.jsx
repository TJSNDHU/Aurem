/**
 * AUREM Customer Detail Page
 * Full profile view for a single tenant customer.
 * Shows profile, plan, usage, performance chart, scan history, and admin notes.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  User, Globe, Mail, Phone, MapPin, Calendar, Clock, Copy, ExternalLink,
  Edit3, Save, X, ChevronLeft, RefreshCw, CheckCircle, AlertCircle,
  TrendingUp, Zap, Shield, FileText, BarChart3, Activity, Heart, Wifi,
  Lock, Wrench, Timer, Plug
} from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const PLAN_COLORS = { starter: '#D4AF37', growth: '#3b82f6', enterprise: '#a855f7' };

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
}

const SIGNAL_META = {
  uptime:        { icon: Wifi,    label: 'Uptime (24h)',       color: '#4ade80' },
  ssl:           { icon: Lock,    label: 'SSL Certificate',    color: '#3b82f6' },
  repairs:       { icon: Wrench,  label: 'Repair Ratio',       color: '#FF6B00' },
  response_time: { icon: Timer,   label: 'Response Time',      color: '#a855f7' },
  integrations:  { icon: Plug,    label: 'Active Integrations', color: '#D4AF37' },
};

function HealthScorePanel({ healthBreakdown, healthScore, recalculating, onRecalculate }) {
  const score = healthBreakdown?.health_score ?? healthScore ?? null;
  const breakdown = healthBreakdown?.breakdown || {};
  const calculatedAt = healthBreakdown?.calculated_at;

  const scoreColor = score >= 80 ? '#4ade80' : score >= 50 ? '#f59e0b' : score != null ? '#ef4444' : '#888';
  const circumference = 2 * Math.PI * 38;
  const offset = score != null ? circumference - (score / 100) * circumference : circumference;

  return (
    <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="health-score-panel">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Heart className="w-4 h-4 text-[#FF6B00]" />
          <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Health Score</span>
        </div>
        <div className="flex items-center gap-3">
          {calculatedAt && (
            <span className="text-[9px] text-[#aaa]">
              Updated {new Date(calculatedAt).toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button
            onClick={onRecalculate}
            disabled={recalculating}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-[#D4AF37] border border-[#D4AF37]/30 rounded-lg hover:bg-[#D4AF37]/5 disabled:opacity-40"
            data-testid="recalculate-health-btn"
          >
            <RefreshCw className={`w-3 h-3 ${recalculating ? 'animate-spin' : ''}`} />
            {recalculating ? 'Calculating...' : 'Recalculate'}
          </button>
        </div>
      </div>

      <div className="flex items-start gap-6">
        {/* Score Ring */}
        <div className="flex-shrink-0 relative w-24 h-24">
          <svg viewBox="0 0 88 88" className="w-full h-full -rotate-90">
            <circle cx="44" cy="44" r="38" fill="none" stroke="rgba(128,128,128,0.08)" strokeWidth="6" />
            <circle
              cx="44" cy="44" r="38" fill="none"
              stroke={scoreColor}
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: 'stroke-dashoffset 0.8s ease' }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold" style={{ color: scoreColor }}>
              {score != null ? score : '—'}
            </span>
            <span className="text-[8px] text-[#888] tracking-wider">/100</span>
          </div>
        </div>

        {/* Signal Breakdown */}
        <div className="flex-1 grid grid-cols-1 gap-2">
          {Object.entries(SIGNAL_META).map(([key, meta]) => {
            const signal = breakdown[key];
            if (!signal) return (
              <div key={key} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'rgba(128,128,128,0.03)' }}>
                <meta.icon className="w-3.5 h-3.5 text-[#ccc]" />
                <span className="text-[10px] text-[#aaa] flex-1">{meta.label}</span>
                <span className="text-[10px] text-[#ccc]">No data</span>
              </div>
            );
            const pct = signal.max > 0 ? (signal.score / signal.max) * 100 : 0;
            const barColor = pct >= 80 ? '#4ade80' : pct >= 50 ? '#f59e0b' : '#ef4444';
            return (
              <div key={key} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: `${meta.color}06` }} data-testid={`health-signal-${key}`}>
                <meta.icon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: meta.color }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[10px] font-medium text-[#555]">{meta.label}</span>
                    <span className="text-[10px] font-bold" style={{ color: barColor }}>{signal.score}/{signal.max}</span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(128,128,128,0.08)' }}>
                    <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: barColor }} />
                  </div>
                  <p className="text-[9px] text-[#999] mt-0.5 truncate">{signal.detail}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function CustomerDetail({ token, tenantId, onBack }) {
  const [customer, setCustomer] = useState(null);
  const [performance, setPerformance] = useState([]);
  const [auditLog, setAuditLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [healthBreakdown, setHealthBreakdown] = useState(null);
  const [recalculating, setRecalculating] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchCustomer = useCallback(async () => {
    try {
      const [cRes, pRes, aRes, hRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/customers/${tenantId}`, { headers }),
        fetch(`${API_URL}/api/admin/customers/${tenantId}/performance`, { headers }),
        fetch(`${API_URL}/api/admin/customers/${tenantId}/audit`, { headers }),
        fetch(`${API_URL}/api/admin/customers/${tenantId}/health-breakdown`, { headers }),
      ]);
      if (cRes.ok) {
        const c = await cRes.json();
        setCustomer(c);
        setNoteDraft(c.notes || '');
      }
      if (pRes.ok) {
        const p = await pRes.json();
        setPerformance(p.scans || []);
      }
      if (aRes.ok) {
        const a = await aRes.json();
        setAuditLog(a.logs || []);
      }
      if (hRes.ok) {
        const h = await hRes.json();
        setHealthBreakdown(h);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [tenantId, token]);

  useEffect(() => { fetchCustomer(); }, [fetchCustomer]);

  const copyBizId = () => {
    if (customer?.business_id) {
      navigator.clipboard.writeText(customer.business_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const openEdit = () => {
    setEditForm({
      full_name: customer.full_name || '',
      phone: customer.phone || '',
      website_url: customer.website_url || '',
      plan: customer.plan || 'starter',
      is_active: customer.is_active !== false,
      company_address: { ...(customer.company_address || {}) },
    });
    setEditing(true);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/customers/${tenantId}`, {
        method: 'PUT', headers,
        body: JSON.stringify(editForm),
      });
      if (res.ok) { setEditing(false); fetchCustomer(); }
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const saveNote = async () => {
    setSavingNote(true);
    try {
      await fetch(`${API_URL}/api/admin/customers/${tenantId}`, {
        method: 'PUT', headers,
        body: JSON.stringify({ notes: noteDraft }),
      });
      fetchCustomer();
    } catch (e) { console.error(e); }
    setSavingNote(false);
  };

  const recalculateHealth = async () => {
    setRecalculating(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/customers/${tenantId}/recalculate-health`, {
        method: 'POST', headers,
      });
      if (res.ok) {
        const data = await res.json();
        setHealthBreakdown(data);
        fetchCustomer();
      }
    } catch (e) { console.error(e); }
    setRecalculating(false);
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center" data-testid="customer-detail-loading">
      <RefreshCw className="w-5 h-5 animate-spin text-[#888]" />
    </div>
  );

  if (!customer) return (
    <div className="flex-1 flex items-center justify-center" data-testid="customer-not-found">
      <div className="text-center">
        <AlertCircle className="w-10 h-10 text-[#888] mx-auto mb-3" style={{ opacity: 0.3 }} />
        <p className="text-sm text-[#888]">Customer not found</p>
        <button onClick={onBack} className="mt-3 text-xs text-[#D4AF37] hover:underline">Back to list</button>
      </div>
    </div>
  );

  const plan = customer.plan || 'starter';
  const planColor = PLAN_COLORS[plan] || '#D4AF37';
  const usage = customer.usage || {};
  const perf = customer.performance || {};
  const addr = customer.company_address || {};
  const usagePct = usage.actions_limit > 0 ? Math.round((usage.actions_used / usage.actions_limit) * 100) : 0;

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="customer-detail">
      <div className="max-w-5xl mx-auto p-6 space-y-5">

        {/* Back button */}
        <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-[#888] hover:text-[#1A1A2E] transition-colors" data-testid="back-to-list">
          <ChevronLeft className="w-3.5 h-3.5" /> Back to Customers
        </button>

        {/* SECTION A — Profile Card */}
        <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="profile-card">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-xl flex items-center justify-center text-lg font-bold" style={{ background: `${planColor}15`, color: planColor }}>
                {customer.company_name?.[0]?.toUpperCase() || 'C'}
              </div>
              <div>
                <h1 className="text-lg font-bold text-[#1A1A2E] tracking-wide">{customer.company_name}</h1>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] font-mono text-[#888] px-2 py-0.5 rounded" style={{ background: 'rgba(128,128,128,0.06)' }}>
                    {customer.business_id}
                  </span>
                  <button onClick={copyBizId} className="text-[#888] hover:text-[#D4AF37]" data-testid="copy-biz-id">
                    {copied ? <CheckCircle className="w-3 h-3 text-[#4ade80]" /> : <Copy className="w-3 h-3" />}
                  </button>
                  <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold ${customer.is_active ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-[#ef4444]/10 text-[#ef4444]'}`}>
                    {customer.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div className="mt-3 space-y-1.5">
                  <p className="text-xs text-[#555] flex items-center gap-2"><User className="w-3 h-3 text-[#888]" />{customer.full_name || '—'}</p>
                  <p className="text-xs text-[#555] flex items-center gap-2"><Mail className="w-3 h-3 text-[#888]" />{customer.email || '—'}</p>
                  <p className="text-xs text-[#555] flex items-center gap-2"><Phone className="w-3 h-3 text-[#888]" />{customer.phone || '—'}</p>
                  <p className="text-xs text-[#555] flex items-center gap-2">
                    <Globe className="w-3 h-3 text-[#888]" />
                    {customer.website_url ? (
                      <a href={customer.website_url} target="_blank" rel="noopener noreferrer" className="text-[#D4AF37] hover:underline flex items-center gap-1">
                        {customer.website_url.replace(/https?:\/\//, '')} <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ) : '—'}
                  </p>
                  <p className="text-xs text-[#555] flex items-center gap-2"><MapPin className="w-3 h-3 text-[#888]" />{[addr.city, addr.province, addr.country].filter(Boolean).join(', ') || '—'}</p>
                </div>
                <div className="flex items-center gap-4 mt-3 text-[10px] text-[#888]">
                  <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> Joined {formatDate(customer.joined_date)}</span>
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Last active {formatDate(customer.last_active)}</span>
                </div>
              </div>
            </div>
            <button onClick={openEdit} className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-[#D4AF37] border border-[#D4AF37]/30 rounded-lg hover:bg-[#D4AF37]/5" data-testid="edit-customer-btn">
              <Edit3 className="w-3 h-3" /> Edit
            </button>
          </div>
        </div>

        {/* SECTION A+ — Health Score Breakdown */}
        <HealthScorePanel
          healthBreakdown={healthBreakdown}
          healthScore={customer.health_score}
          recalculating={recalculating}
          onRecalculate={recalculateHealth}
        />

        {/* SECTION B — Plan + Usage side by side */}
        <div className="grid grid-cols-2 gap-4">
          {/* Subscription Card */}
          <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="plan-card">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4" style={{ color: planColor }} />
              <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Subscription</span>
            </div>
            <div className="text-lg font-bold uppercase tracking-wider" style={{ color: planColor }}>{plan} Plan</div>
            <div className="text-2xl font-bold text-[#1A1A2E] mt-1">${customer.plan_price_cad} <span className="text-xs font-normal text-[#888]">CAD/month</span></div>
            <div className="mt-3 space-y-1 text-[10px] text-[#555]">
              <p>Started: {formatDate(customer.plan_started)}</p>
              <p>Renews: {formatDate(customer.plan_ends)}</p>
              <p>Status: <span className={customer.plan_status === 'active' ? 'text-[#4ade80] font-bold' : 'text-[#ef4444] font-bold'}>{customer.plan_status}</span></p>
              <p>Billing: {customer.billing_cycle}</p>
            </div>
          </div>

          {/* Daily Usage Card */}
          <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="usage-card">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-[#FF6B00]" />
              <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Today's Usage</span>
            </div>
            <div className="mb-3">
              <div className="flex items-baseline justify-between mb-1">
                <span className="text-xs text-[#555]">Actions</span>
                <span className="text-xs font-bold text-[#1A1A2E]">{usage.actions_used}/{usage.actions_limit}</span>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(128,128,128,0.1)' }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${usagePct}%`, background: usagePct > 80 ? '#ef4444' : usagePct > 50 ? '#f59e0b' : '#4ade80' }} />
              </div>
              <p className="text-[10px] text-[#888] mt-1">{usage.actions_remaining} remaining</p>
            </div>
            <div className="flex items-baseline justify-between mb-1">
              <span className="text-xs text-[#555]">Pipeline Runs</span>
              <span className="text-xs font-bold text-[#1A1A2E]">{usage.pipeline_runs_today}/{usage.pipeline_runs_limit}</span>
            </div>
            <p className="text-[10px] text-[#888] mt-2">Resets at midnight ({usage.reset_cycle})</p>
          </div>
        </div>

        {/* SECTION C — Performance History */}
        <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="performance-section">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[#D4AF37]" />
              <span className="text-xs font-bold text-[#1A1A2E] tracking-wide">Performance Since Day One</span>
            </div>
            <span className="text-[10px] text-[#888]">{formatDate(customer.joined_date)} - Today</span>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-5 gap-3 mb-4">
            {[
              { label: 'Total Scans', value: perf.total_scans, color: '#D4AF37' },
              { label: 'Leads Found', value: perf.leads_found, color: '#3b82f6' },
              { label: 'Converted', value: perf.leads_converted, color: '#4ade80' },
              { label: 'Issues Fixed', value: perf.issues_fixed, color: '#FF6B00' },
              { label: 'Avg Score', value: perf.website_score, color: '#a855f7' },
            ].map((s, i) => (
              <div key={i} className="text-center p-2.5 rounded-lg" style={{ background: `${s.color}08` }}>
                <div className="text-lg font-bold" style={{ color: s.color }}>{s.value || 0}</div>
                <div className="text-[9px] text-[#888]">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Chart */}
          {performance.length > 1 ? (
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={performance}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.1)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#888' }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#888' }} />
                  <Tooltip contentStyle={{ fontSize: 10, background: '#fff', border: '1px solid #eee', borderRadius: 8 }} />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <Line type="monotone" dataKey="overall" stroke="#D4AF37" strokeWidth={2} dot={{ r: 3 }} name="Overall" />
                  <Line type="monotone" dataKey="security" stroke="#FF6B00" strokeWidth={1.5} dot={false} name="Security" />
                  <Line type="monotone" dataKey="seo" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="SEO" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : performance.length === 1 ? (
            <div className="text-center py-6 text-xs text-[#888]">
              1 scan recorded (score: {performance[0]?.overall || 0}). More data points needed for chart.
            </div>
          ) : (
            <div className="text-center py-6 text-xs text-[#888]">No scan data yet.</div>
          )}

          {/* Scan History Table */}
          {performance.length > 0 && (
            <div className="mt-4">
              <h4 className="text-[10px] font-bold text-[#888] tracking-wider uppercase mb-2">Scan History</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="text-[#888] text-left border-b border-[#eee]">
                      <th className="pb-2 font-bold">Date</th>
                      <th className="pb-2 font-bold text-center">Overall</th>
                      <th className="pb-2 font-bold text-center">Perf</th>
                      <th className="pb-2 font-bold text-center">SEO</th>
                      <th className="pb-2 font-bold text-center">Security</th>
                      <th className="pb-2 font-bold text-center">Issues</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...performance].reverse().slice(0, 20).map((s, i) => (
                      <tr key={i} className="border-b border-[#f5f5f5]">
                        <td className="py-1.5 text-[#1A1A2E]">{s.date}</td>
                        <td className="py-1.5 text-center font-bold" style={{ color: s.overall >= 80 ? '#4ade80' : s.overall >= 50 ? '#f59e0b' : '#ef4444' }}>{s.overall}</td>
                        <td className="py-1.5 text-center text-[#888]">{s.performance || '—'}</td>
                        <td className="py-1.5 text-center text-[#888]">{s.seo || '—'}</td>
                        <td className="py-1.5 text-center text-[#888]">{s.security || '—'}</td>
                        <td className="py-1.5 text-center">{s.issues > 0 ? <span className="text-[#ef4444] font-bold">{s.issues}</span> : <span className="text-[#4ade80]">0</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Admin Notes */}
        <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="admin-notes">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-[#888]" />
            <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Admin Notes</span>
          </div>
          <textarea
            value={noteDraft}
            onChange={e => setNoteDraft(e.target.value)}
            placeholder="Private admin notes about this customer..."
            className="w-full h-24 px-3 py-2 text-xs text-[#1A1A2E] bg-white/50 border border-[#FF6B00]/15 rounded-lg outline-none focus:border-[#D4AF37]/50 resize-none"
            data-testid="admin-notes-textarea"
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[9px] text-[#888]">
              {customer.notes ? `Last saved: ${formatDate(customer.last_active)}` : 'No notes saved yet'}
            </span>
            <button onClick={saveNote} disabled={savingNote || noteDraft === (customer.notes || '')} className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-white bg-[#D4AF37] rounded-lg hover:opacity-90 disabled:opacity-40" data-testid="save-notes-btn">
              <Save className="w-3 h-3" /> {savingNote ? 'Saving...' : 'Save Notes'}
            </button>
          </div>
        </div>

        {/* Audit Log */}
        {auditLog.length > 0 && (
          <div className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl" data-testid="audit-log">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-[#888]" />
              <span className="text-[10px] font-bold tracking-[1.5px] text-[#888] uppercase">Change History</span>
            </div>
            <div className="space-y-2">
              {auditLog.slice(0, 15).map((log, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'rgba(128,128,128,0.03)' }}>
                  <Edit3 className="w-3 h-3 text-[#888] flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-[10px] text-[#1A1A2E]">
                      <strong>{log.field}</strong> changed from <em>{log.old_value || '(empty)'}</em> to <em>{log.new_value}</em>
                    </span>
                  </div>
                  <span className="text-[9px] text-[#888] flex-shrink-0">{log.changed_by} - {formatDate(log.changed_at)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Edit Modal */}
      {editing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[10000]" data-testid="edit-modal">
          <div className="bg-white rounded-2xl w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-[#1A1A2E]">Edit Customer</h3>
              <button onClick={() => setEditing(false)}><X className="w-5 h-5 text-[#888]" /></button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] text-[#888] mb-1 tracking-wider">FULL NAME</label>
                <input value={editForm.full_name} onChange={e => setEditForm(f => ({ ...f, full_name: e.target.value }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-full-name" />
              </div>
              <div>
                <label className="block text-[10px] text-[#888] mb-1 tracking-wider">PHONE</label>
                <input value={editForm.phone} onChange={e => setEditForm(f => ({ ...f, phone: e.target.value }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-phone" />
              </div>
              <div>
                <label className="block text-[10px] text-[#888] mb-1 tracking-wider">WEBSITE URL</label>
                <input value={editForm.website_url} onChange={e => setEditForm(f => ({ ...f, website_url: e.target.value }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-website" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-[10px] text-[#888] mb-1 tracking-wider">CITY</label>
                  <input value={editForm.company_address?.city || ''} onChange={e => setEditForm(f => ({ ...f, company_address: { ...f.company_address, city: e.target.value } }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-city" />
                </div>
                <div>
                  <label className="block text-[10px] text-[#888] mb-1 tracking-wider">PROVINCE</label>
                  <input value={editForm.company_address?.province || ''} onChange={e => setEditForm(f => ({ ...f, company_address: { ...f.company_address, province: e.target.value } }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-province" />
                </div>
                <div>
                  <label className="block text-[10px] text-[#888] mb-1 tracking-wider">COUNTRY</label>
                  <input value={editForm.company_address?.country || ''} onChange={e => setEditForm(f => ({ ...f, company_address: { ...f.company_address, country: e.target.value } }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-country" />
                </div>
              </div>
              <div>
                <label className="block text-[10px] text-[#888] mb-1 tracking-wider">PLAN</label>
                <select value={editForm.plan} onChange={e => setEditForm(f => ({ ...f, plan: e.target.value }))} className="w-full px-3 py-2 text-xs border border-[#eee] rounded-lg outline-none focus:border-[#D4AF37]" data-testid="edit-plan">
                  <option value="starter">Starter ($97/mo)</option>
                  <option value="growth">Growth ($297/mo)</option>
                  <option value="enterprise">Enterprise ($997/mo)</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" checked={editForm.is_active} onChange={e => setEditForm(f => ({ ...f, is_active: e.target.checked }))} id="edit-active" data-testid="edit-active" />
                <label htmlFor="edit-active" className="text-xs text-[#555]">Active customer</label>
              </div>

              {/* Read-only fields */}
              <div className="p-3 rounded-lg" style={{ background: 'rgba(128,128,128,0.04)' }}>
                <p className="text-[10px] text-[#888] mb-1">READ ONLY</p>
                <p className="text-[10px] text-[#555]">Tenant ID: {customer.tenant_id}</p>
                <p className="text-[10px] text-[#555]">Business ID: {customer.business_id}</p>
                <p className="text-[10px] text-[#555]">Email: {customer.email}</p>
                <p className="text-[10px] text-[#555]">Joined: {formatDate(customer.joined_date)}</p>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button onClick={() => setEditing(false)} className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#eee] rounded-lg">Cancel</button>
              <button onClick={saveEdit} disabled={saving} className="flex-1 px-4 py-2.5 text-xs font-semibold text-white bg-[#D4AF37] rounded-lg hover:opacity-90 disabled:opacity-50" data-testid="save-edit-btn">
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
