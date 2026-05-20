/**
 * AUREM Empty State Components
 * Professional "no data yet" states for day-1 clients
 */
import React from 'react';
import { Inbox, BarChart3, Users, Zap, Activity, Brain, Target, Clock } from 'lucide-react';

const EmptyState = ({ icon: Icon, title, subtitle, actionLabel, onAction, testId }) => (
  <div className="flex flex-col items-center justify-center py-16 px-6 text-center" data-testid={testId || 'empty-state'}>
    <div className="size-14 rounded-2xl flex items-center justify-center mb-4"
      style={{ background: 'linear-gradient(135deg, rgba(255,107,0,0.08), rgba(212,175,55,0.08))', border: '1px solid rgba(255,107,0,0.12)' }}>
      <Icon className="size-6" style={{ color: '#FF6B00' }} />
    </div>
    <h3 className="text-sm font-semibold mb-1" style={{ color: '#1A1A2E' }}>{title}</h3>
    <p className="text-[11px] max-w-xs mb-4" style={{ color: '#888' }}>{subtitle}</p>
    {actionLabel && onAction && (
      <button onClick={onAction} data-testid={`${testId}-action`}
        className="px-4 py-2 rounded-lg text-[11px] font-bold text-white transition-all hover:opacity-90"
        style={{ background: 'linear-gradient(135deg, #FF6B00, #D4AF37)' }}>
        {actionLabel}
      </button>
    )}
  </div>
);

export const EmptyLeads = ({ onTrigger }) => (
  <EmptyState
    icon={Users}
    title="Scout hasn't found leads yet"
    subtitle="Morning Brief runs at 7am to scan your pipeline. You can also trigger Scout manually."
    actionLabel="Trigger Scout Now"
    onAction={onTrigger}
    testId="empty-leads"
  />
);

export const EmptyPipeline = ({ onTrigger }) => (
  <EmptyState
    icon={Activity}
    title="No pipeline runs yet"
    subtitle="AUREM's OODA pipeline processes leads, scores them, and takes action autonomously."
    actionLabel="Run Pipeline Now"
    onAction={onTrigger}
    testId="empty-pipeline"
  />
);

export const EmptyInbox = () => (
  <EmptyState
    icon={Inbox}
    title="Unified inbox is empty"
    subtitle="Connect WhatsApp, Gmail, or SMS channels to see conversations here."
    testId="empty-inbox"
  />
);

export const EmptyRevenue = () => (
  <EmptyState
    icon={BarChart3}
    title="No revenue data yet"
    subtitle="Revenue forecasts will appear once you have active leads in your pipeline."
    testId="empty-revenue"
  />
);

export const EmptyMemory = () => (
  <EmptyState
    icon={Brain}
    title="Memory is learning"
    subtitle="AUREM stores patterns from every interaction. Knowledge builds over time."
    testId="empty-memory"
  />
);

export const EmptyApprovals = () => (
  <EmptyState
    icon={Clock}
    title="No pending approvals"
    subtitle="High-stakes actions (payments, security changes) require your sign-off before execution."
    testId="empty-approvals"
  />
);

export const EmptySentinel = () => (
  <EmptyState
    icon={Zap}
    title="Sentinel is monitoring"
    subtitle="No anomalies detected. System health checks run every 10 minutes."
    testId="empty-sentinel"
  />
);

export const EmptyASIEvolve = () => (
  <EmptyState
    icon={Target}
    title="No evolutions yet"
    subtitle="ASI-Evolve observes pipeline failures and synthesizes improvements. It gets smarter with every run."
    testId="empty-asi-evolve"
  />
);

export default EmptyState;
