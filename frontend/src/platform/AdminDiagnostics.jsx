/**
 * AdminDiagnostics — merged Sentinel + Auto-Fixer (Phase 3)
 *
 * Sidebar still says "Diagnostics" → /admin/sentinel.
 * This page hosts BOTH dashboards in tabs without rewriting either component.
 */
import React, { useState } from 'react';
import { Shield, Wrench } from 'lucide-react';
import AdminSentinelClient from './AdminSentinelClient';
import AdminAutoFixer from './AdminAutoFixer';

const TABS = [
  { id: 'sentinel', label: 'Sentinel · Client Errors', icon: Shield, accent: '#F0A030' },
  { id: 'fixer',    label: 'Auto-Fixer · Repair Queue', icon: Wrench, accent: '#22C55E' },
];

const AdminDiagnostics = () => {
  const [tab, setTab] = useState(() => {
    try { return localStorage.getItem('aurem_diag_tab') || 'sentinel'; } catch { return 'sentinel'; }
  });
  const switchTab = (id) => {
    setTab(id);
    try { localStorage.setItem('aurem_diag_tab', id); } catch { /* ignore */ }
  };

  return (
    <div data-testid="admin-diagnostics" style={{ minHeight: '100vh', background: '#06060A', color: '#EDE8DF' }}>
      {/* Header + tab strip */}
      <div style={{ borderBottom: '1px solid rgba(212,175,55,0.10)', padding: '20px 32px 0', background: '#0B0B10' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <Shield style={{ width: 14, height: 14, color: '#F0A030' }} />
          <span style={{ fontSize: 9, color: '#7A7468', letterSpacing: '0.3em', textTransform: 'uppercase' }}>Health</span>
        </div>
        <h1 style={{ fontFamily: "'Cinzel', serif", fontSize: 22, letterSpacing: '0.08em', margin: '2px 0 4px' }}>
          Diagnostics
        </h1>
        <p style={{ fontSize: 11, color: '#7A7468', marginBottom: 16 }}>
          Unified view: Sentinel client-error surfacing + Auto-Fixer repair queue.
        </p>
        <div style={{ display: 'flex', gap: 4 }}>
          {TABS.map((t) => {
            const I = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => switchTab(t.id)}
                data-testid={`diagnostics-tab-${t.id}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '8px 14px',
                  borderRadius: '8px 8px 0 0',
                  background: active ? `${t.accent}1A` : 'transparent',
                  border: 'none',
                  borderBottom: active ? `2px solid ${t.accent}` : '2px solid transparent',
                  color: active ? '#EDE8DF' : '#7A7468',
                  fontSize: 11, letterSpacing: '0.05em', cursor: 'pointer',
                  transition: 'background 100ms',
                }}>
                <I style={{ width: 12, height: 12 }} />
                {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Pane */}
      <div data-testid={`diagnostics-pane-${tab}`}>
        {tab === 'sentinel' && <AdminSentinelClient />}
        {tab === 'fixer'    && <AdminAutoFixer />}
      </div>
    </div>
  );
};

export default AdminDiagnostics;
