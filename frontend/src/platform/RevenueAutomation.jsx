/**
 * Phase E: Revenue Automation Dashboard
 * Full invoice management, payment tracking, revenue metrics, forecast
 * Payment methods: bank cheque, e-transfer, cash, Stripe (future)
 */
import React, { useState, useEffect, useCallback , useMemo } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import {
  DollarSign, TrendingUp, TrendingDown, BarChart3, Activity,
  FileText, Download, RefreshCw, ArrowUpRight, ArrowDownRight,
  Zap, Users, MessageSquare, Globe, Mail, HardDrive,
  ChevronRight, AlertCircle, CheckCircle, Plus, Send, Trash2,
  CreditCard, Building2, Banknote, X, Clock, Eye, Share2,
  Bell, BellRing, LinkIcon, Loader2, Briefcase
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const PAYMENT_METHODS = [
  { value: 'e_transfer', label: 'E-Transfer', icon: Zap },
  { value: 'cheque', label: 'Bank Cheque', icon: Building2 },
  { value: 'cash', label: 'Cash', icon: Banknote },
  { value: 'stripe', label: 'Stripe (Future)', icon: CreditCard },
];

const STATUS_COLORS = {
  draft: { bg: 'rgba(107,114,128,0.1)', text: '#6b7280' },
  sent: { bg: 'rgba(59,130,246,0.1)', text: '#3b82f6' },
  awaiting_payment: { bg: 'rgba(245,158,11,0.1)', text: '#f59e0b' },
  paid: { bg: 'rgba(16,185,129,0.1)', text: '#10b981' },
  overdue: { bg: 'rgba(239,68,68,0.1)', text: '#ef4444' },
  cancelled: { bg: 'rgba(107,114,128,0.1)', text: '#9ca3af' },
};

function MetricCard({ label, value, change, icon: Icon, color, prefix = '' }) {
  const isPositive = change >= 0;
  return (
    <div className="aurem-glass-card p-5 rounded-2xl" data-testid={`metric-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>{label}</span>
        <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: `${color}18` }}>
          <Icon size={16} style={{ color }} />
        </div>
      </div>
      <div className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>{prefix}{typeof value === 'number' ? value.toLocaleString('en-CA', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : value}</div>
      {change !== undefined && change !== null && (
        <div className="flex items-center gap-1 mt-1.5">
          {isPositive ? <ArrowUpRight size={13} className="text-emerald-500" /> : <ArrowDownRight size={13} className="text-red-400" />}
          <span className={`text-xs font-medium ${isPositive ? 'text-emerald-500' : 'text-red-400'}`}>{Math.abs(change)}%</span>
          <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>vs last month</span>
        </div>
      )}
    </div>
  );
}

function MiniBar({ used, total, color }) {
  const pct = total > 0 ? Math.min((used / total) * 100, 100) : 0;
  return (
    <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: 'rgba(128,128,128,0.15)' }}>
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: pct > 85 ? '#ef4444' : color }} />
    </div>
  );
}

export default function RevenueAutomation({ token }) {
  const [tab, setTab] = useState('overview');
  const [dashboard, setDashboard] = useState(null);
  const [usage, setUsage] = useState(null);
  const [invoiceData, setInvoiceData] = useState({ invoices: [], total: 0, summary: {} });
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [dashRes, usageRes, invRes, forecastRes] = await Promise.allSettled([
        fetch(`${API}/api/revenue/dashboard`, { headers }),
        fetch(`${API}/api/revenue/usage/summary`, { headers }),
        fetch(`${API}/api/revenue/invoices?limit=50`, { headers }),
        fetch(`${API}/api/revenue/forecast`, { headers }),
      ]);
      if (dashRes.status === 'fulfilled' && dashRes.value.ok) setDashboard(await dashRes.value.json());
      if (usageRes.status === 'fulfilled' && usageRes.value.ok) setUsage(await usageRes.value.json());
      if (invRes.status === 'fulfilled' && invRes.value.ok) setInvoiceData(await invRes.value.json());
      if (forecastRes.status === 'fulfilled' && forecastRes.value.ok) setForecast(await forecastRes.value.json());
    } catch (e) { console.error('Revenue fetch error', e); }
    setLoading(false);
  }, [headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  // iter 271 — live refresh every 15s (pauses in background)
  useLivePolling(fetchAll, 15000);

  const [reminders, setReminders] = useState({ overdue: [], approaching_due: [], overdue_count: 0, approaching_count: 0 });
  const [showAutoInvoice, setShowAutoInvoice] = useState(false);

  const fetchReminders = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/revenue/reminders`, { headers });
      if (res.ok) setReminders(await res.json());
    } catch (e) { console.error('Reminders fetch error', e); }
  }, [headers]);

  useEffect(() => { if (tab === 'reminders') fetchReminders(); }, [tab, fetchReminders]);

  const tabs = [
    { id: 'overview', label: 'Revenue Overview' },
    { id: 'invoices', label: 'Invoices', badge: invoiceData.total },
    { id: 'reminders', label: 'Reminders', badge: reminders.overdue_count || 0 },
    { id: 'usage', label: 'Usage Metering' },
    { id: 'forecast', label: 'Forecast' },
  ];

  // Calculate invoice stats
  const invSummary = invoiceData.summary || {};
  const totalPaid = invSummary.paid?.amount || 0;
  const totalPending = (invSummary.sent?.amount || 0) + (invSummary.awaiting_payment?.amount || 0);
  const totalOverdue = invSummary.overdue?.amount || 0;

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="revenue-automation">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>Revenue Automation</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>Invoicing, payments & real-time revenue intelligence</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => { setShowAutoInvoice(true); setTab('invoices'); }} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all" style={{ background: 'rgba(139,91,214,0.1)', color: '#8B5CF6' }} data-testid="auto-invoice-btn">
            <Briefcase size={14} /> Auto from Deal
          </button>
          <button onClick={() => { setShowCreateInvoice(true); setTab('invoices'); }} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] hover:opacity-90 transition-all" data-testid="create-invoice-btn">
            <Plus size={14} /> New Invoice
          </button>
          <button onClick={fetchAll} disabled={loading} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all" style={{ background: '#FF6B0018', color: '#FF6B00' }} data-testid="refresh-revenue">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(128,128,128,0.1)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
            className={`px-4 py-2 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${tab === t.id ? 'shadow-sm' : ''}`}
            style={{ background: tab === t.id ? 'var(--aurem-card, rgba(255,255,255,0.9))' : 'transparent', color: tab === t.id ? '#FF6B00' : 'var(--aurem-text-secondary)' }}>
            {t.label}
            {t.badge > 0 && <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-[rgba(61,58,57,0.25)] text-[#FF6B00]">{t.badge}</span>}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard label="MRR" value={dashboard?.mrr || 0} change={dashboard?.growth_pct} icon={DollarSign} color="#FF6B00" prefix="$" />
            <MetricCard label="Collected" value={totalPaid} icon={CheckCircle} color="#10b981" prefix="$" />
            <MetricCard label="Pending" value={totalPending} icon={Clock} color="#f59e0b" prefix="$" />
            <MetricCard label="Overdue" value={totalOverdue} icon={AlertCircle} color="#ef4444" prefix="$" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <MetricCard label="Total Invoices" value={invoiceData.total} icon={FileText} color="#3b82f6" />
            <MetricCard label="Churn Rate" value={`${dashboard?.churn_rate || 0}%`} icon={dashboard?.churn_rate > 5 ? TrendingDown : Activity} color={dashboard?.churn_rate > 5 ? '#ef4444' : '#D4AF37'} />
          </div>

          {/* Quick Payment Method Stats */}
          <div className="aurem-glass-card p-5 rounded-2xl">
            <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--aurem-text)' }}>Payment Methods Accepted</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {PAYMENT_METHODS.map(m => (
                <div key={m.value} className="flex items-center gap-2 p-3 rounded-xl" style={{ background: 'rgba(128,128,128,0.06)', border: '1px solid rgba(128,128,128,0.1)' }}>
                  <m.icon size={16} style={{ color: m.value === 'stripe' ? '#9ca3af' : '#FF6B00' }} />
                  <span className="text-xs font-medium" style={{ color: m.value === 'stripe' ? 'var(--aurem-text-secondary)' : 'var(--aurem-text)' }}>{m.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Daily Revenue Chart */}
          {dashboard?.daily_revenue?.length > 0 && (
            <div className="aurem-glass-card p-5 rounded-2xl">
              <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--aurem-text)' }}>Daily Revenue (Last 30 Days)</h3>
              <div className="flex items-end gap-1 h-32">
                {dashboard.daily_revenue.map((d, i) => {
                  const max = Math.max(...dashboard.daily_revenue.map(x => x.amount), 1);
                  const h = (d.amount / max) * 100;
                  return (
                    <div key={i} className="flex-1 group relative" title={`${d.date}: $${d.amount}`}>
                      <div className="w-full rounded-t transition-all duration-300 hover:opacity-80" style={{ height: `${Math.max(h, 4)}%`, background: '#FF6B00', minHeight: '2px' }} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Invoices Tab */}
      {tab === 'invoices' && (
        <div className="space-y-4">
          {showAutoInvoice && (
            <AutoInvoiceForm token={token} onClose={() => setShowAutoInvoice(false)} onCreated={() => { setShowAutoInvoice(false); fetchAll(); }} />
          )}

          {showCreateInvoice && !showAutoInvoice && (
            <CreateInvoiceForm token={token} onClose={() => setShowCreateInvoice(false)} onCreated={() => { setShowCreateInvoice(false); fetchAll(); }} />
          )}

          {selectedInvoice && !showAutoInvoice && (
            <InvoiceDetail invoice={selectedInvoice} token={token} onClose={() => setSelectedInvoice(null)} onUpdate={fetchAll} />
          )}

          {!showCreateInvoice && !selectedInvoice && !showAutoInvoice && (
            <>
              {/* Invoice Status Summary */}
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                {['draft', 'sent', 'awaiting_payment', 'paid', 'overdue', 'cancelled'].map(s => (
                  <div key={s} className="text-center p-2.5 rounded-xl" style={{ background: STATUS_COLORS[s].bg }}>
                    <div className="text-lg font-bold" style={{ color: STATUS_COLORS[s].text }}>{invSummary[s]?.count || 0}</div>
                    <div className="text-[10px] font-medium uppercase" style={{ color: STATUS_COLORS[s].text }}>{s.replace('_', ' ')}</div>
                  </div>
                ))}
              </div>

              {/* Invoice List */}
              <div className="aurem-glass-card rounded-2xl overflow-hidden">
                <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>All Invoices ({invoiceData.total})</h3>
                  <button onClick={() => setShowCreateInvoice(true)} className="flex items-center gap-1.5 text-xs font-medium" style={{ color: '#FF6B00' }} data-testid="add-invoice-inline">
                    <Plus size={13} /> Create
                  </button>
                </div>

                {(invoiceData.invoices || []).length === 0 ? (
                  <div className="p-12 text-center">
                    <FileText size={36} className="mx-auto mb-3" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.4 }} />
                    <p className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>No invoices yet</p>
                    <p className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>Create your first invoice to start tracking payments</p>
                    <button onClick={() => setShowCreateInvoice(true)} className="mt-4 px-4 py-2 rounded-lg text-xs font-medium text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355]" data-testid="create-first-invoice">
                      <Plus size={13} className="inline mr-1" /> Create Invoice
                    </button>
                  </div>
                ) : (
                  <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
                    {(invoiceData.invoices || []).map(inv => {
                      const sc = STATUS_COLORS[inv.status] || STATUS_COLORS.draft;
                      return (
                        <div key={inv.id} className="px-4 py-3 flex items-center gap-4 hover:bg-white/5 transition-colors cursor-pointer" onClick={() => setSelectedInvoice(inv)} data-testid={`invoice-row-${inv.invoice_number}`}>
                          <FileText size={16} style={{ color: 'var(--aurem-text-secondary)' }} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{inv.invoice_number}</span>
                              <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{inv.customer_name}</span>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{inv.created_at?.slice(0, 10)}</span>
                              <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{inv.payment_method?.replace('_', '-')}</span>
                            </div>
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase" style={{ background: sc.bg, color: sc.text }}>{inv.status?.replace('_', ' ')}</span>
                          <span className="text-sm font-bold" style={{ color: 'var(--aurem-text)' }}>${inv.total?.toLocaleString()}</span>
                          <Eye size={14} style={{ color: 'var(--aurem-text-secondary)' }} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Reminders Tab */}
      {tab === 'reminders' && (
        <RemindersPanel reminders={reminders} token={token} onRefresh={fetchReminders} />
      )}

      {/* Usage Tab */}
      {tab === 'usage' && (
        <div className="space-y-5">
          <div className="aurem-glass-card p-5 rounded-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>Current Period Usage</h3>
              <span className="text-xs px-2.5 py-1 rounded-full font-medium" style={{ background: '#FF6B0018', color: '#FF6B00' }}>
                {(usage?.plan || 'trial').toUpperCase()} Plan
              </span>
            </div>
            <div className="space-y-4">
              {[
                { key: 'ai_messages', label: 'AI Messages', icon: MessageSquare, color: '#8B5CF6' },
                { key: 'api_calls', label: 'API Calls', icon: Globe, color: '#3b82f6' },
                { key: 'emails', label: 'Emails Sent', icon: Mail, color: '#D4AF37' },
                { key: 'storage_mb', label: 'Storage (MB)', icon: HardDrive, color: '#FF6B00' },
              ].map(item => {
                const used = usage?.usage?.[item.key] || 0;
                const limit = usage?.limits?.[item.key] || 1;
                return (
                  <div key={item.key} data-testid={`usage-${item.key}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <item.icon size={14} style={{ color: item.color }} />
                        <span className="text-xs font-medium" style={{ color: 'var(--aurem-text-secondary)' }}>{item.label}</span>
                      </div>
                      <span className="text-xs font-mono" style={{ color: 'var(--aurem-text-secondary)' }}>{used.toLocaleString()} / {limit >= 999999 ? 'Unlimited' : limit.toLocaleString()}</span>
                    </div>
                    <MiniBar used={used} total={limit} color={item.color} />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Forecast Tab */}
      {tab === 'forecast' && forecast && (
        <div className="space-y-5">
          <div className="aurem-glass-card p-5 rounded-2xl">
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--aurem-text)' }}>Revenue Forecast</h3>
            <p className="text-xs mb-4" style={{ color: 'var(--aurem-text-secondary)' }}>Based on 6-month historical trend (${forecast.monthly_trend >= 0 ? '+' : ''}${forecast.monthly_trend}/mo)</p>
            <div className="space-y-3">
              {[...(forecast.historical || []), ...(forecast.forecast || [])].map((item, i) => {
                const isProjected = !!item.projected;
                const val = item.revenue ?? item.projected ?? 0;
                const max = Math.max(...[...(forecast.historical || []).map(h => h.revenue), ...(forecast.forecast || []).map(f => f.projected)], 1);
                return (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs font-mono w-16 shrink-0" style={{ color: isProjected ? '#8B5CF6' : 'var(--aurem-text-secondary)' }}>{item.month}</span>
                    <div className="flex-1 h-6 rounded-lg overflow-hidden" style={{ background: 'rgba(128,128,128,0.1)' }}>
                      <div className="h-full rounded-lg transition-all duration-500" style={{
                        width: `${Math.max((val / max) * 100, 2)}%`,
                        background: isProjected ? 'linear-gradient(90deg, #8B5CF6, #a78bfa)' : '#FF6B00',
                        opacity: isProjected ? 0.7 : 1
                      }} />
                    </div>
                    <span className="text-xs font-medium w-20 text-right" style={{ color: isProjected ? '#8B5CF6' : 'var(--aurem-text)' }}>
                      ${val.toLocaleString()}{isProjected ? '*' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
      {tab === 'forecast' && !forecast && (
        <div className="aurem-glass-card p-8 rounded-2xl text-center">
          <BarChart3 size={36} className="mx-auto mb-3" style={{ color: 'var(--aurem-text-secondary)', opacity: 0.4 }} />
          <p className="text-sm" style={{ color: 'var(--aurem-text-secondary)' }}>Forecast data loading…</p>
        </div>
      )}
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* CREATE INVOICE FORM                                        */
/* ═══════════════════════════════════════════════════════════ */
function CreateInvoiceForm({ token, onClose, onCreated }) {
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('e_transfer');
  const [payInstructions, setPayInstructions] = useState('');
  const [taxRate, setTaxRate] = useState(13);
  const [dueDays, setDueDays] = useState(30);
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState([{ description: '', quantity: 1, unit_price: 0 }]);
  const [saving, setSaving] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#FF6B00]";

  const addItem = () => setItems([...items, { description: '', quantity: 1, unit_price: 0 }]);
  const removeItem = (i) => items.length > 1 && setItems(items.filter((_, idx) => idx !== i));
  const updateItem = (i, field, val) => {
    const newItems = [...items];
    newItems[i] = { ...newItems[i], [field]: field === 'description' ? val : parseFloat(val) || 0 };
    setItems(newItems);
  };

  const subtotal = items.reduce((s, it) => s + (it.quantity * it.unit_price), 0);
  const tax = subtotal * (taxRate / 100);
  const total = subtotal + tax;

  const submit = async () => {
    if (!customerName.trim() || items.every(i => !i.description.trim())) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/revenue/invoices`, {
        method: 'POST', headers,
        body: JSON.stringify({
          customer_name: customerName,
          customer_email: customerEmail || null,
          customer_phone: customerPhone || null,
          line_items: items.filter(i => i.description.trim()),
          tax_rate: taxRate,
          payment_method: paymentMethod,
          payment_instructions: payInstructions || null,
          due_days: dueDays,
          notes: notes || null,
          currency: 'CAD',
        }),
      });
      if (res.ok) onCreated();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="aurem-glass-card rounded-2xl p-6 space-y-5" data-testid="create-invoice-form">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>New Invoice</h2>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>

      {/* Customer Info */}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Customer Name *</label>
          <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Business or person name" className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-customer-name" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Email</label>
          <input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="email@example.com" className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-customer-email" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Phone</label>
          <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="+1 (555) 000-0000" className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-customer-phone" />
        </div>
      </div>

      {/* Line Items */}
      <div>
        <label className="block text-[10px] mb-2 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Line Items</label>
        <div className="space-y-2">
          {items.map((item, i) => (
            <div key={i} className="flex items-center gap-2" data-testid={`line-item-${i}`}>
              <input value={item.description} onChange={(e) => updateItem(i, 'description', e.target.value)} placeholder="Description" className={`flex-1 ${inputCls}`} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} />
              <input type="number" value={item.quantity} onChange={(e) => updateItem(i, 'quantity', e.target.value)} placeholder="Qty" className={`w-20 ${inputCls}`} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} />
              <input type="number" value={item.unit_price} onChange={(e) => updateItem(i, 'unit_price', e.target.value)} placeholder="Price" className={`w-24 ${inputCls}`} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} />
              <span className="text-sm font-mono w-20 text-right" style={{ color: 'var(--aurem-text)' }}>${(item.quantity * item.unit_price).toFixed(2)}</span>
              <button onClick={() => removeItem(i)} className="p-1 text-red-400 hover:bg-red-400/10 rounded"><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
        <button onClick={addItem} className="mt-2 text-xs font-medium flex items-center gap-1" style={{ color: '#FF6B00' }} data-testid="add-line-item"><Plus size={13} /> Add Item</button>
      </div>

      {/* Payment & Tax */}
      <div className="grid grid-cols-4 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Payment Method</label>
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)} className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-payment-method">
            {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Tax Rate %</label>
          <input type="number" value={taxRate} onChange={(e) => setTaxRate(parseFloat(e.target.value) || 0)} className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-tax-rate" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Due In (days)</label>
          <input type="number" value={dueDays} onChange={(e) => setDueDays(parseInt(e.target.value) || 30)} className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="invoice-due-days" />
        </div>
        <div className="flex flex-col justify-end">
          <div className="p-3 rounded-lg text-right" style={{ background: 'rgba(255,107,0,0.05)' }}>
            <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>Sub: ${subtotal.toFixed(2)} | Tax: ${tax.toFixed(2)}</div>
            <div className="text-lg font-bold" style={{ color: '#FF6B00' }}>${total.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* Notes & Instructions */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Payment Instructions</label>
          <textarea value={payInstructions} onChange={(e) => setPayInstructions(e.target.value)} rows={2} placeholder="E.g., Send e-Transfer to payments@mybiz.com" className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)', resize: 'none' }} />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Notes</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} placeholder="Internal notes or terms" className={inputCls} style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)', resize: 'none' }} />
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-medium" style={{ color: 'var(--aurem-text-secondary)' }}>Cancel</button>
        <button onClick={submit} disabled={saving || !customerName.trim()} className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] disabled:opacity-50 hover:opacity-90 transition-all" data-testid="submit-invoice-btn">
          <FileText size={14} /> {saving ? 'Creating...' : 'Create Invoice'}
        </button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* INVOICE DETAIL VIEW                                        */
/* ═══════════════════════════════════════════════════════════ */
function InvoiceDetail({ invoice, token, onClose, onUpdate }) {
  const [showPayment, setShowPayment] = useState(false);
  const [payMethod, setPayMethod] = useState(invoice.payment_method || 'e_transfer');
  const [payRef, setPayRef] = useState('');
  const [payAmount, setPayAmount] = useState(invoice.amount_due || invoice.total || 0);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [shareUrl, setShareUrl] = useState('');
  const [sharing, setSharing] = useState(false);
  const [sendingReminder, setSendingReminder] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
  const sc = STATUS_COLORS[invoice.status] || STATUS_COLORS.draft;

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${API}/api/revenue/invoices/${invoice.id}/pdf`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${invoice.invoice_number || 'invoice'}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } catch (e) { console.error('PDF download error', e); }
    finally { setDownloading(false); }
  };

  const getShareLink = async () => {
    setSharing(true);
    try {
      const res = await fetch(`${API}/api/revenue/invoices/${invoice.id}/share`, { headers });
      if (res.ok) {
        const data = await res.json();
        setShareUrl(data.share_url);
        if (navigator.clipboard) await navigator.clipboard.writeText(data.share_url);
      }
    } catch (e) { console.error('Share link error', e); }
    finally { setSharing(false); }
  };

  const sendReminder = async () => {
    setSendingReminder(true);
    try {
      await fetch(`${API}/api/revenue/reminders/send/${invoice.id}`, { method: 'POST', headers });
    } catch (e) { console.error('Reminder error', e); }
    finally { setSendingReminder(false); }
  };

  const updateStatus = async (newStatus) => {
    try {
      await fetch(`${API}/api/revenue/invoices/${invoice.id}/status`, {
        method: 'PUT', headers,
        body: JSON.stringify({ status: newStatus }),
      });
      onUpdate(); onClose();
    } catch (e) { console.error(e); }
  };

  const recordPayment = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/revenue/invoices/${invoice.id}/payment`, {
        method: 'POST', headers,
        body: JSON.stringify({ payment_method: payMethod, amount: payAmount, reference: payRef }),
      });
      onUpdate(); onClose();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const deleteInvoice = async () => {
    try {
      await fetch(`${API}/api/revenue/invoices/${invoice.id}`, { method: 'DELETE', headers });
      onUpdate(); onClose();
    } catch (e) { console.error(e); }
  };

  return (
    <div className="aurem-glass-card rounded-2xl p-6 space-y-5" data-testid="invoice-detail">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>{invoice.invoice_number}</h2>
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase" style={{ background: sc.bg, color: sc.text }}>{invoice.status?.replace('_', ' ')}</span>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10"><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>

      {/* Customer & Dates */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>Customer</div>
          <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{invoice.customer_name}</div>
          {invoice.customer_email && <div className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{invoice.customer_email}</div>}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>Created</div>
          <div className="text-sm" style={{ color: 'var(--aurem-text)' }}>{invoice.created_at?.slice(0, 10)}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>Due Date</div>
          <div className="text-sm" style={{ color: 'var(--aurem-text)' }}>{invoice.due_date?.slice(0, 10)}</div>
        </div>
      </div>

      {/* Line Items */}
      <div className="rounded-xl overflow-hidden" style={{ border: '1px solid rgba(128,128,128,0.15)' }}>
        <div className="grid grid-cols-12 gap-2 px-4 py-2 text-[10px] uppercase tracking-wider" style={{ background: 'rgba(128,128,128,0.06)', color: 'var(--aurem-text-secondary)' }}>
          <div className="col-span-6">Description</div>
          <div className="col-span-2 text-right">Qty</div>
          <div className="col-span-2 text-right">Price</div>
          <div className="col-span-2 text-right">Amount</div>
        </div>
        {(invoice.line_items || []).map((item, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 px-4 py-2.5" style={{ borderTop: '1px solid rgba(128,128,128,0.08)' }}>
            <div className="col-span-6 text-sm" style={{ color: 'var(--aurem-text)' }}>{item.description}</div>
            <div className="col-span-2 text-sm text-right" style={{ color: 'var(--aurem-text-secondary)' }}>{item.quantity}</div>
            <div className="col-span-2 text-sm text-right" style={{ color: 'var(--aurem-text-secondary)' }}>${item.unit_price?.toFixed(2)}</div>
            <div className="col-span-2 text-sm font-medium text-right" style={{ color: 'var(--aurem-text)' }}>${item.amount?.toFixed(2)}</div>
          </div>
        ))}
        <div className="px-4 py-3 space-y-1" style={{ background: 'rgba(128,128,128,0.04)', borderTop: '1px solid rgba(128,128,128,0.15)' }}>
          <div className="flex justify-between text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>
            <span>Subtotal</span><span>${invoice.subtotal?.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>
            <span>Tax ({invoice.tax_rate}%)</span><span>${invoice.tax_amount?.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm font-bold pt-1" style={{ color: 'var(--aurem-text)', borderTop: '1px solid rgba(128,128,128,0.15)' }}>
            <span>Total</span><span>${invoice.total?.toFixed(2)} {invoice.currency}</span>
          </div>
          {invoice.amount_paid > 0 && (
            <div className="flex justify-between text-xs text-emerald-500 font-medium">
              <span>Paid</span><span>-${invoice.amount_paid?.toFixed(2)}</span>
            </div>
          )}
          {invoice.amount_due > 0 && invoice.status !== 'paid' && (
            <div className="flex justify-between text-sm font-bold text-amber-500">
              <span>Amount Due</span><span>${invoice.amount_due?.toFixed(2)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Payment Info */}
      {invoice.payment_instructions && (
        <div className="p-3 rounded-xl" style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.12)' }}>
          <div className="text-[10px] uppercase tracking-wider mb-1 font-bold" style={{ color: '#3b82f6' }}>Payment Instructions ({invoice.payment_method?.replace('_', ' ')})</div>
          <div className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{invoice.payment_instructions}</div>
        </div>
      )}

      {/* Payment History */}
      {invoice.payments?.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider mb-2" style={{ color: 'var(--aurem-text-secondary)' }}>Payment History</div>
          {invoice.payments.map((p, i) => (
            <div key={i} className="flex items-center gap-3 p-2 rounded-lg mb-1" style={{ background: 'rgba(16,185,129,0.06)' }}>
              <CheckCircle size={14} className="text-emerald-500" />
              <span className="text-xs font-medium text-emerald-500">${p.amount?.toFixed(2)}</span>
              <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{p.method?.replace('_', ' ')} {p.reference ? `(${p.reference})` : ''}</span>
              <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-text-secondary)' }}>{p.recorded_at?.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Record Payment Form */}
      {showPayment && invoice.status !== 'paid' && (
        <div className="p-4 rounded-xl space-y-3" style={{ background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.15)' }} data-testid="record-payment-form">
          <div className="text-xs font-bold" style={{ color: '#10b981' }}>Record Payment</div>
          <div className="grid grid-cols-3 gap-2">
            <select value={payMethod} onChange={(e) => setPayMethod(e.target.value)} className="px-3 py-2 rounded-lg text-sm border" style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }}>
              {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <input type="number" value={payAmount} onChange={(e) => setPayAmount(parseFloat(e.target.value) || 0)} placeholder="Amount" className="px-3 py-2 rounded-lg text-sm border" style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="payment-amount" />
            <input value={payRef} onChange={(e) => setPayRef(e.target.value)} placeholder="Reference # (optional)" className="px-3 py-2 rounded-lg text-sm border" style={{ background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' }} data-testid="payment-reference" />
          </div>
          <button onClick={recordPayment} disabled={saving} className="px-4 py-2 rounded-lg text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50" data-testid="confirm-payment-btn">
            {saving ? 'Recording...' : 'Confirm Payment'}
          </button>
        </div>
      )}

      {/* Share Link Banner */}
      {shareUrl && (
        <div className="p-3 rounded-xl flex items-center gap-3" style={{ background: 'rgba(255,107,0,0.05)', border: '1px solid rgba(255,107,0,0.1)' }} data-testid="share-link-banner">
          <LinkIcon size={14} style={{ color: '#FF6B00' }} />
          <input readOnly value={shareUrl} className="flex-1 text-xs font-mono bg-transparent outline-none" style={{ color: 'var(--aurem-text)' }} data-testid="share-link-input" />
          <button onClick={() => navigator.clipboard?.writeText(shareUrl)} className="text-[10px] font-bold px-2 py-1 rounded" style={{ color: '#FF6B00', background: 'rgba(61,58,57,0.25)' }}>Copy</button>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap pt-2" style={{ borderTop: '1px solid rgba(128,128,128,0.15)' }}>
        {/* PDF Download */}
        <button onClick={downloadPdf} disabled={downloading} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all" style={{ background: 'rgba(61,58,57,0.15)', color: '#FF6B00' }} data-testid="download-pdf-btn">
          {downloading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />} {downloading ? 'Generating...' : 'Download PDF'}
        </button>

        {/* Share Link */}
        <button onClick={getShareLink} disabled={sharing} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all" style={{ background: 'rgba(59,130,246,0.08)', color: '#3b82f6' }} data-testid="share-link-btn">
          {sharing ? <Loader2 size={13} className="animate-spin" /> : <Share2 size={13} />} Share Link
        </button>

        {/* Send Reminder (for overdue/sent invoices) */}
        {['sent', 'awaiting_payment', 'overdue'].includes(invoice.status) && (
          <button onClick={sendReminder} disabled={sendingReminder} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all" style={{ background: 'rgba(245,158,11,0.08)', color: '#f59e0b' }} data-testid="send-reminder-btn">
            {sendingReminder ? <Loader2 size={13} className="animate-spin" /> : <Bell size={13} />} {sendingReminder ? 'Sending...' : 'Send Reminder'}
          </button>
        )}

        {invoice.status === 'draft' && (
          <button onClick={() => updateStatus('sent')} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700" data-testid="send-invoice-btn">
            <Send size={13} /> Send Invoice
          </button>
        )}
        {['sent', 'awaiting_payment', 'overdue'].includes(invoice.status) && (
          <button onClick={() => setShowPayment(!showPayment)} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700" data-testid="record-payment-btn">
            <DollarSign size={13} /> Record Payment
          </button>
        )}
        {['draft', 'sent'].includes(invoice.status) && (
          <button onClick={() => updateStatus('cancelled')} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium" style={{ color: '#ef4444', border: '1px solid rgba(239,68,68,0.3)' }} data-testid="cancel-invoice-btn">
            <X size={13} /> Cancel
          </button>
        )}
        {['draft', 'cancelled'].includes(invoice.status) && (
          <button onClick={deleteInvoice} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium" style={{ color: '#ef4444' }} data-testid="delete-invoice-btn">
            <Trash2 size={13} /> Delete
          </button>
        )}
        <button onClick={onClose} className="ml-auto px-4 py-2 rounded-lg text-xs font-medium" style={{ color: 'var(--aurem-text-secondary)' }}>Close</button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* AUTO-INVOICE FROM DEAL                                      */
/* ═══════════════════════════════════════════════════════════ */
function AutoInvoiceForm({ token, onClose, onCreated }) {
  const [dealName, setDealName] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [amount, setAmount] = useState(0);
  const [description, setDescription] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('e_transfer');
  const [taxRate, setTaxRate] = useState(13);
  const [dueDays, setDueDays] = useState(30);
  const [saving, setSaving] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
  const inputCls = "w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:ring-1 focus:ring-[#8B5CF6]";
  const inputStyle = { background: 'var(--aurem-input-bg, #fff)', borderColor: 'var(--aurem-input-border, #e5e7eb)', color: 'var(--aurem-text)' };

  const taxAmount = amount * (taxRate / 100);
  const total = amount + taxAmount;

  const submit = async () => {
    if (!dealName.trim() || !customerName.trim() || amount <= 0) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/revenue/auto-invoice`, {
        method: 'POST', headers,
        body: JSON.stringify({
          deal_name: dealName, customer_name: customerName,
          customer_email: customerEmail || null, customer_phone: customerPhone || null,
          amount, description: description || null,
          payment_method: paymentMethod, tax_rate: taxRate, due_days: dueDays,
        }),
      });
      if (res.ok) onCreated();
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  return (
    <div className="aurem-glass-card rounded-2xl p-6 space-y-5" data-testid="auto-invoice-form">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(139,91,214,0.12)' }}>
            <Briefcase size={16} style={{ color: '#8B5CF6' }} />
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--aurem-text)' }}>Auto-Invoice from Deal</h2>
            <p className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>Create an invoice automatically when a deal closes</p>
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"><X size={18} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Deal Name *</label>
          <input value={dealName} onChange={(e) => setDealName(e.target.value)} placeholder="Q1 Website Redesign" className={inputCls} style={inputStyle} data-testid="auto-deal-name" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Customer Name *</label>
          <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="ABC Corp" className={inputCls} style={inputStyle} data-testid="auto-customer-name" />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Email</label>
          <input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="client@company.com" className={inputCls} style={inputStyle} data-testid="auto-customer-email" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Phone</label>
          <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="+1 555-000-0000" className={inputCls} style={inputStyle} data-testid="auto-customer-phone" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Deal Amount * ($)</label>
          <input type="number" value={amount} onChange={(e) => setAmount(parseFloat(e.target.value) || 0)} placeholder="0.00" className={inputCls} style={inputStyle} data-testid="auto-amount" />
        </div>
      </div>

      <div>
        <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Description (optional)</label>
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Services rendered for deal" className={`${inputCls}`} style={inputStyle} data-testid="auto-description" />
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Payment Method</label>
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)} className={inputCls} style={inputStyle} data-testid="auto-payment-method">
            {PAYMENT_METHODS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Tax Rate %</label>
          <input type="number" value={taxRate} onChange={(e) => setTaxRate(parseFloat(e.target.value) || 0)} className={inputCls} style={inputStyle} data-testid="auto-tax-rate" />
        </div>
        <div>
          <label className="block text-[10px] mb-1 uppercase tracking-wider" style={{ color: 'var(--aurem-text-secondary)' }}>Due In (days)</label>
          <input type="number" value={dueDays} onChange={(e) => setDueDays(parseInt(e.target.value) || 30)} className={inputCls} style={inputStyle} data-testid="auto-due-days" />
        </div>
        <div className="flex flex-col justify-end">
          <div className="p-3 rounded-lg text-right" style={{ background: 'rgba(139,91,214,0.06)' }}>
            <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>Sub: ${amount.toFixed(2)} | Tax: ${taxAmount.toFixed(2)}</div>
            <div className="text-lg font-bold" style={{ color: '#8B5CF6' }}>${total.toFixed(2)}</div>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-medium" style={{ color: 'var(--aurem-text-secondary)' }}>Cancel</button>
        <button onClick={submit} disabled={saving || !dealName.trim() || !customerName.trim() || amount <= 0}
          className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50 hover:opacity-90 transition-all"
          style={{ background: 'linear-gradient(135deg, #8B5CF6, #6D28D9)' }} data-testid="submit-auto-invoice-btn">
          <Briefcase size={14} /> {saving ? 'Creating...' : 'Generate Invoice'}
        </button>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* REMINDERS PANEL                                             */
/* ═══════════════════════════════════════════════════════════ */
function RemindersPanel({ reminders, token, onRefresh }) {
  const [sendingId, setSendingId] = useState(null);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const sendReminder = async (invoiceId) => {
    setSendingId(invoiceId);
    try {
      await fetch(`${API}/api/revenue/reminders/send/${invoiceId}`, { method: 'POST', headers });
      onRefresh();
    } catch (e) { console.error(e); }
    finally { setSendingId(null); }
  };

  const loadHistory = async () => {
    try {
      const res = await fetch(`${API}/api/revenue/reminders/history?limit=20`, { headers });
      if (res.ok) { const data = await res.json(); setHistory(data.reminders || []); }
    } catch (e) { console.error(e); }
    setShowHistory(true);
  };

  const overdue = reminders.overdue || [];
  const approaching = reminders.approaching_due || [];

  return (
    <div className="space-y-5" data-testid="reminders-panel">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="aurem-glass-card p-5 rounded-2xl">
          <div className="flex items-center gap-2 mb-2">
            <BellRing size={16} style={{ color: '#ef4444' }} />
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#ef4444' }}>Overdue</span>
          </div>
          <div className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>{reminders.overdue_count || 0}</div>
          <div className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>
            ${(reminders.overdue_total || 0).toLocaleString()} outstanding
          </div>
        </div>
        <div className="aurem-glass-card p-5 rounded-2xl">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={16} style={{ color: '#f59e0b' }} />
            <span className="text-xs font-medium uppercase tracking-wider" style={{ color: '#f59e0b' }}>Due Soon</span>
          </div>
          <div className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>{reminders.approaching_count || 0}</div>
          <div className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>
            ${(reminders.approaching_total || 0).toLocaleString()} within 3 days
          </div>
        </div>
      </div>

      {/* Overdue Invoices */}
      {overdue.length > 0 && (
        <div className="aurem-glass-card rounded-2xl overflow-hidden">
          <div className="p-4 flex items-center gap-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
            <BellRing size={14} style={{ color: '#ef4444' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#ef4444' }}>Overdue Invoices ({overdue.length})</h3>
          </div>
          <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
            {overdue.map(inv => (
              <div key={inv.id} className="px-4 py-3 flex items-center gap-4" data-testid={`overdue-${inv.invoice_number}`}>
                <AlertCircle size={16} className="text-red-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{inv.invoice_number} — {inv.customer_name}</div>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>Due: {inv.due_date?.slice(0, 10)} | {inv.customer_email || 'No email'}</div>
                </div>
                <span className="text-sm font-bold text-red-400">${inv.amount_due?.toLocaleString()}</span>
                <button onClick={() => sendReminder(inv.id)} disabled={sendingId === inv.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold text-white bg-red-500 hover:bg-red-600 disabled:opacity-50 transition-all" data-testid={`remind-${inv.id}`}>
                  {sendingId === inv.id ? <Loader2 size={11} className="animate-spin" /> : <Bell size={11} />}
                  {sendingId === inv.id ? 'Sending...' : 'Send Reminder'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Approaching Due */}
      {approaching.length > 0 && (
        <div className="aurem-glass-card rounded-2xl overflow-hidden">
          <div className="p-4 flex items-center gap-2" style={{ borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
            <Clock size={14} style={{ color: '#f59e0b' }} />
            <h3 className="text-sm font-semibold" style={{ color: '#f59e0b' }}>Due Within 3 Days ({approaching.length})</h3>
          </div>
          <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
            {approaching.map(inv => (
              <div key={inv.id} className="px-4 py-3 flex items-center gap-4" data-testid={`approaching-${inv.invoice_number}`}>
                <Clock size={16} className="text-amber-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{inv.invoice_number} — {inv.customer_name}</div>
                  <div className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>Due: {inv.due_date?.slice(0, 10)} | {inv.customer_email || 'No email'}</div>
                </div>
                <span className="text-sm font-bold" style={{ color: '#f59e0b' }}>${inv.amount_due?.toLocaleString()}</span>
                <button onClick={() => sendReminder(inv.id)} disabled={sendingId === inv.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all" style={{ color: '#f59e0b', background: 'rgba(245,158,11,0.1)' }} data-testid={`remind-approaching-${inv.id}`}>
                  {sendingId === inv.id ? <Loader2 size={11} className="animate-spin" /> : <Bell size={11} />}
                  Nudge
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {overdue.length === 0 && approaching.length === 0 && (
        <div className="aurem-glass-card p-12 rounded-2xl text-center">
          <CheckCircle size={36} className="mx-auto mb-3 text-emerald-500" style={{ opacity: 0.5 }} />
          <p className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>All clear! No overdue invoices.</p>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-text-secondary)' }}>Payment reminders will appear here when invoices become overdue.</p>
        </div>
      )}

      {/* Reminder History */}
      <div className="flex items-center gap-2">
        <button onClick={loadHistory} className="flex items-center gap-1.5 text-xs font-medium" style={{ color: '#FF6B00' }} data-testid="view-reminder-history">
          <Clock size={13} /> View Reminder History
        </button>
        <button onClick={onRefresh} className="flex items-center gap-1.5 text-xs font-medium" style={{ color: 'var(--aurem-text-secondary)' }} data-testid="refresh-reminders">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {showHistory && (
        <div className="aurem-glass-card rounded-2xl overflow-hidden" data-testid="reminder-history">
          <div className="p-4" style={{ borderBottom: '1px solid rgba(128,128,128,0.15)' }}>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>Reminder History</h3>
          </div>
          {history.length === 0 ? (
            <div className="p-6 text-center text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>No reminders sent yet.</div>
          ) : (
            <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
              {history.map((r, i) => (
                <div key={r.id || i} className="px-4 py-2.5 flex items-center gap-3">
                  <Mail size={13} style={{ color: '#3b82f6' }} />
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium" style={{ color: 'var(--aurem-text)' }}>{r.invoice_number}</span>
                    <span className="text-[10px] ml-2" style={{ color: 'var(--aurem-text-secondary)' }}>{r.customer_name}</span>
                  </div>
                  <span className="text-xs font-medium" style={{ color: '#ef4444' }}>${r.amount_due?.toLocaleString()}</span>
                  <span className="text-[10px]" style={{ color: 'var(--aurem-text-secondary)' }}>{r.sent_at?.slice(0, 10)}</span>
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>{r.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
