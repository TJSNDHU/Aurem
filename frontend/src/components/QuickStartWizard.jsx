import React, { useState, useEffect } from 'react';
import { Globe, TrendingUp, MessageSquare, Check, X, ChevronRight, Sparkles, DollarSign, Phone } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const STEP_ICONS = {
  connect_crm: Globe,
  setup_pipeline: TrendingUp,
  activate_ora: MessageSquare,
  review_catalog: DollarSign,
  configure_voice: Phone,
};

const QuickStartWizard = ({ token, onNavigate }) => {
  const [data, setData] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (token) fetchStatus();
  }, [token]);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/onboarding/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const d = await res.json();
        setData(d);
        setDismissed(d.dismissed || d.all_complete);
      }
    } catch (e) {
      console.error('Onboarding fetch failed:', e);
    } finally {
      setLoading(false);
    }
  };

  const completeStep = async (stepId) => {
    try {
      await fetch(`${API_URL}/api/onboarding/complete-step`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ step_id: stepId }),
      });
      fetchStatus();
    } catch (e) {
      console.error('Complete step failed:', e);
    }
  };

  const dismissWizard = async () => {
    try {
      await fetch(`${API_URL}/api/onboarding/dismiss`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      setDismissed(true);
    } catch (e) {
      console.error('Dismiss failed:', e);
    }
  };

  const handleStepClick = (step) => {
    if (!step.completed) completeStep(step.id);
    if (onNavigate && step.nav_target) onNavigate(step.nav_target);
  };

  if (loading || dismissed || !data) return null;

  const progressPct = Math.round(data.progress * 100);

  return (
    <div
      data-testid="quick-start-wizard"
      className="mx-4 mt-4 rounded-2xl overflow-hidden"
      style={{
        background: 'var(--aurem-card-bg, rgba(30,32,38,0.95))',
        border: '1px solid var(--aurem-border)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.15)',
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #2D7A4A, #1B5E35)' }}>
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Quick Start</h3>
            <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{data.completed_count}/{data.total} steps complete</p>
          </div>
        </div>
        <button
          data-testid="dismiss-wizard-btn"
          onClick={dismissWizard}
          className="p-1.5 rounded-lg transition-colors hover:bg-black/5"
          style={{ color: 'var(--aurem-body-secondary)' }}
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="mx-5 mb-3 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--aurem-border)' }}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${progressPct}%`, background: 'linear-gradient(90deg, #2D7A4A, #4ADE80)' }}
        />
      </div>

      {/* Steps */}
      <div className="px-4 pb-4 space-y-2">
        {data.steps.map((step) => {
          const Icon = STEP_ICONS[step.id] || Globe;
          return (
            <button
              key={step.id}
              data-testid={`wizard-step-${step.id}`}
              onClick={() => handleStepClick(step)}
              className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all duration-200 group"
              style={{
                background: step.completed ? 'rgba(45,122,74,0.12)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${step.completed ? 'rgba(45,122,74,0.25)' : 'var(--aurem-border)'}`,
              }}
            >
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-all"
                style={{
                  background: step.completed ? 'linear-gradient(135deg, #2D7A4A, #4ADE80)' : 'rgba(255,255,255,0.05)',
                  border: step.completed ? 'none' : '1px solid var(--aurem-border)',
                }}
              >
                {step.completed ? (
                  <Check className="w-4 h-4 text-white" />
                ) : (
                  <Icon className="w-4 h-4" style={{ color: 'var(--aurem-body-secondary)' }} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className="text-xs font-semibold truncate"
                  style={{
                    color: step.completed ? 'var(--aurem-body-secondary)' : 'var(--aurem-heading)',
                    textDecoration: step.completed ? 'line-through' : 'none',
                  }}
                >
                  {step.title}
                </p>
                <p className="text-[10px] truncate" style={{ color: 'var(--aurem-body-secondary)' }}>
                  {step.description}
                </p>
              </div>
              {!step.completed && (
                <ChevronRight
                  className="w-4 h-4 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ color: '#2D7A4A' }}
                />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default QuickStartWizard;
