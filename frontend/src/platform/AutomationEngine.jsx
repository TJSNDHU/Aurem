/**
 * AUREM Automation Engine
 * Build and deploy automated workflows with triggers, actions, and conditions
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, Plus, Play, Pause, Trash2, Copy, RefreshCw,
  ChevronRight, Clock, CheckCircle, AlertCircle, XCircle,
  Settings, Filter, Search, ArrowRight, Activity, Shield,
  Mail, MessageCircle, Globe, Users, BarChart3, X, Edit
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const WORKFLOW_TEMPLATES = [
  {
    id: 'lead-nurture',
    name: 'Lead Nurture Sequence',
    description: 'Automatically follow up with new leads via email and WhatsApp',
    trigger: 'New Lead Created',
    actions: ['Send Welcome Email', 'Wait 2 Days', 'Send WhatsApp Follow-up', 'Assign to Agent'],
    category: 'Sales',
    color: '#D4AF37'
  },
  {
    id: 'deal-alert',
    name: 'Deal Stage Alert',
    description: 'Notify team when deals move to critical stages',
    trigger: 'Deal Stage Changed',
    actions: ['Check Stage', 'Send Slack Notification', 'Update CRM', 'Log Activity'],
    category: 'CRM',
    color: '#4ade80'
  },
  {
    id: 'customer-onboard',
    name: 'Customer Onboarding',
    description: 'Welcome new customers with automated setup flow',
    trigger: 'Customer Created',
    actions: ['Send Welcome Pack', 'Create Workspace', 'Schedule Intro Call', 'Assign CSM'],
    category: 'Operations',
    color: '#3b82f6'
  },
  {
    id: 'churn-prevention',
    name: 'Churn Prevention',
    description: 'Detect at-risk customers and trigger retention workflows',
    trigger: 'Sentiment Score < 0.3',
    actions: ['Alert Account Manager', 'Send Survey', 'Offer Discount', 'Schedule Call'],
    category: 'Retention',
    color: '#ef4444'
  },
  {
    id: 'invoice-reminder',
    name: 'Invoice Reminder',
    description: 'Auto-send payment reminders for overdue invoices',
    trigger: 'Invoice Overdue',
    actions: ['Send Email Reminder', 'Wait 3 Days', 'Send SMS', 'Escalate to Manager'],
    category: 'Billing',
    color: '#f59e0b'
  }
];

export default function AutomationEngine({ token }) {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('workflows');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  const fetchWorkflows = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/automations/workflows`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWorkflows(data.workflows || []);
      }
    } catch {
      setWorkflows([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleToggleWorkflow = (id) => {
    setWorkflows(prev => prev.map(w =>
      w.id === id ? { ...w, status: w.status === 'active' ? 'paused' : 'active' } : w
    ));
  };

  const handleDeleteWorkflow = (id) => {
    setWorkflows(prev => prev.filter(w => w.id !== id));
  };

  const handleCreateFromTemplate = (template) => {
    const newWorkflow = {
      id: `wf-${Date.now()}`,
      name: template.name,
      description: template.description,
      trigger: template.trigger,
      actions: template.actions,
      status: 'paused',
      runs_today: 0,
      success_rate: 100,
      created_at: new Date().toISOString(),
      category: template.category,
      color: template.color
    };
    setWorkflows(prev => [newWorkflow, ...prev]);
    setShowCreateModal(false);
    setSelectedTemplate(null);
  };

  const stats = {
    total: workflows.length,
    active: workflows.filter(w => w.status === 'active').length,
    runs_today: workflows.reduce((sum, w) => sum + (w.runs_today || 0), 0),
    success_rate: workflows.length > 0
      ? Math.round(workflows.reduce((sum, w) => sum + (w.success_rate || 0), 0) / workflows.length)
      : 100
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="automation-engine-loading">
        <div className="flex items-center gap-3 text-[#666]">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading automations...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="automation-engine">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Automation Engine</h1>
            <p className="text-xs text-[#5a5a72]">Build and deploy automated workflows with triggers, actions, and conditions</p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            data-testid="create-workflow-btn"
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90 transition-opacity"
          >
            <Plus className="w-3.5 h-3.5" />
            New Workflow
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: 'TOTAL WORKFLOWS', value: stats.total, icon: Zap, color: '#D4AF37' },
            { label: 'ACTIVE', value: stats.active, icon: Play, color: '#4ade80' },
            { label: 'RUNS TODAY', value: stats.runs_today, icon: Activity, color: '#D4AF37' },
            { label: 'SUCCESS RATE', value: `${stats.success_rate}%`, icon: CheckCircle, color: '#4ade80' }
          ].map((stat, idx) => (
            <div key={idx} className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                <span className="text-[9px] text-[#555] tracking-wider">{stat.label}</span>
              </div>
              <div className="text-2xl font-semibold font-mono" style={{ color: stat.color }}>{stat.value}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white/80 backdrop-blur-sm p-1 rounded-lg border border-[#FF6B00]/20 w-fit">
          {[
            { id: 'workflows', label: 'My Workflows', icon: Zap },
            { id: 'templates', label: 'Templates', icon: Copy },
            { id: 'history', label: 'Run History', icon: Clock }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`automation-tab-${tab.id}`}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs transition-all ${
                activeTab === tab.id
                  ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30'
                  : 'text-[#666] hover:text-[#555]'
              }`}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'workflows' && (
          <>
            {workflows.length > 0 ? (
              <div className="space-y-3">
                {workflows.map(wf => (
                  <div
                    key={wf.id}
                    data-testid={`workflow-${wf.id}`}
                    className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl hover:border-[#D4AF37]/20 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${wf.color || '#D4AF37'}15` }}>
                          <Zap className="w-5 h-5" style={{ color: wf.color || '#D4AF37' }} />
                        </div>
                        <div>
                          <h3 className="text-sm font-medium text-[#1A1A2E]">{wf.name}</h3>
                          <p className="text-[11px] text-[#5a5a72] mt-0.5">{wf.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          wf.status === 'active'
                            ? 'bg-[#4ade80]/10 text-[#4ade80]'
                            : 'bg-[#f59e0b]/10 text-[#f59e0b]'
                        }`}>
                          {wf.status === 'active' ? 'Active' : 'Paused'}
                        </span>
                      </div>
                    </div>

                    {/* Flow visualization */}
                    <div className="flex items-center gap-2 mb-4 overflow-x-auto py-2">
                      <div className="flex items-center gap-1 px-2.5 py-1 bg-[#D4AF37]/10 border border-[#D4AF37]/20 rounded text-[10px] text-[#D4AF37] whitespace-nowrap">
                        <Zap className="w-3 h-3" />
                        {wf.trigger}
                      </div>
                      {(wf.actions || []).map((action, i) => (
                        <React.Fragment key={i}>
                          <ArrowRight className="w-3 h-3 text-[#333] flex-shrink-0" />
                          <div className="px-2.5 py-1 bg-white/50 border border-[#FF6B00]/15 rounded text-[10px] text-[#888] whitespace-nowrap">
                            {action}
                          </div>
                        </React.Fragment>
                      ))}
                    </div>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 text-[10px] text-[#555]">
                        <span>{wf.runs_today || 0} runs today</span>
                        <span>{wf.success_rate || 100}% success</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleToggleWorkflow(wf.id)}
                          className={`p-1.5 rounded-md transition-colors ${
                            wf.status === 'active'
                              ? 'text-[#f59e0b] hover:bg-[#f59e0b]/10'
                              : 'text-[#4ade80] hover:bg-[#4ade80]/10'
                          }`}
                        >
                          {wf.status === 'active' ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleDeleteWorkflow(wf.id)}
                          className="p-1.5 rounded-md text-[#555] hover:text-[#ef4444] hover:bg-[#ef4444]/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-16 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl text-center">
                <Zap className="w-10 h-10 text-[#333] mx-auto mb-4" />
                <h3 className="text-sm font-medium text-[#1A1A2E] mb-2">No workflows yet</h3>
                <p className="text-[11px] text-[#5a5a72] mb-6">Create your first automation from a template or build from scratch</p>
                <button
                  onClick={() => { setActiveTab('templates'); }}
                  className="px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
                >
                  Browse Templates
                </button>
              </div>
            )}
          </>
        )}

        {activeTab === 'templates' && (
          <div className="grid grid-cols-2 gap-4">
            {WORKFLOW_TEMPLATES.map(template => (
              <div
                key={template.id}
                data-testid={`template-${template.id}`}
                className="p-5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl hover:border-[#D4AF37]/20 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${template.color}15` }}>
                      <Zap className="w-5 h-5" style={{ color: template.color }} />
                    </div>
                    <div>
                      <h3 className="text-sm font-medium text-[#1A1A2E]">{template.name}</h3>
                      <span className="text-[9px] text-[#5a5a72] tracking-wider">{template.category.toUpperCase()}</span>
                    </div>
                  </div>
                </div>
                <p className="text-[11px] text-[#888] mb-4 leading-relaxed">{template.description}</p>

                <div className="flex items-center gap-1 mb-4 text-[10px] text-[#555]">
                  <span className="text-[#D4AF37]">{template.trigger}</span>
                  <ArrowRight className="w-3 h-3" />
                  <span>{template.actions.length} actions</span>
                </div>

                <button
                  onClick={() => handleCreateFromTemplate(template)}
                  data-testid={`use-template-${template.id}`}
                  className="w-full py-2 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity"
                >
                  Use This Template
                </button>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#FF6B00]/20">
              <h3 className="text-xs text-[#555] tracking-wider">EXECUTION HISTORY</h3>
              <button onClick={fetchWorkflows} className="text-[#555] hover:text-[#D4AF37] transition-colors" data-testid="refresh-history-btn">
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
            {workflows.filter(w => w.runs_today > 0).length > 0 ? (
              <div className="divide-y divide-[#141414]">
                {workflows.filter(w => w.runs_today > 0).map((wf, idx) => (
                  <div key={idx} className="flex items-center justify-between px-4 py-3 hover:bg-white/40" data-testid={`history-entry-${idx}`}>
                    <div className="flex items-center gap-3">
                      <CheckCircle className="w-4 h-4 text-[#4ade80]" />
                      <span className="text-xs text-[#1A1A2E]">{wf.name}</span>
                    </div>
                    <div className="flex items-center gap-4 text-[10px] text-[#555]">
                      <span className="text-[#D4AF37] font-medium">{wf.runs_today} runs today</span>
                      <span>{wf.success_rate || 0}% success</span>
                      <span className={`px-1.5 py-0.5 rounded text-[9px] ${wf.status === 'active' ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-[#f59e0b]/10 text-[#f59e0b]'}`}>{wf.status}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-10 text-center">
                <Clock className="w-8 h-8 text-[#333] mx-auto mb-3" />
                <p className="text-sm text-[#555]">No execution history</p>
                <p className="text-[11px] text-[#444] mt-1">Create and activate workflows to see run history</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
          <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-sm font-medium text-[#1A1A2E]">New Workflow</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-[#555] hover:text-[#555]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-[#5a5a72] mb-4">Choose a template to get started:</p>
            <div className="space-y-2 max-h-[400px] overflow-auto">
              {WORKFLOW_TEMPLATES.map(t => (
                <button
                  key={t.id}
                  onClick={() => handleCreateFromTemplate(t)}
                  className="w-full flex items-center gap-3 p-4 bg-white/50 border border-[#FF6B00]/15 rounded-xl hover:border-[#D4AF37]/30 transition-colors text-left"
                >
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${t.color}15` }}>
                    <Zap className="w-4 h-4" style={{ color: t.color }} />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-[#1A1A2E]">{t.name}</p>
                    <p className="text-[10px] text-[#5a5a72]">{t.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
