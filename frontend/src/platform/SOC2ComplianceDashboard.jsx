/**
 * AUREM SOC 2 Compliance Dashboard
 * Kill Switch + Audit Trail + RBAC Matrix + Encryption Evidence + Data Deletion
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Shield, Power, AlertTriangle, Eye, Lock, Trash2, FileText, Activity, Users, ChevronDown, ChevronUp, RefreshCw, XCircle, CheckCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const SOC2ComplianceDashboard = ({ token }) => {
  const [summary, setSummary] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditStats, setAuditStats] = useState(null);
  const [rbacMatrix, setRbacMatrix] = useState(null);
  const [encryptionEvidence, setEncryptionEvidence] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [killSwitchLoading, setKillSwitchLoading] = useState(false);
  const [deleteTenantId, setDeleteTenantId] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteResult, setDeleteResult] = useState(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [expandedLog, setExpandedLog] = useState(null);

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/summary`, { headers });
      if (res.ok) setSummary(await res.json());
    } catch (e) { console.error('Summary fetch error:', e); }
  }, [token]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/audit-trail?hours=168&limit=50`, { headers });
      if (res.ok) {
        const data = await res.json();
        setAuditLogs(data.logs || []);
      }
    } catch (e) { console.error('Audit logs fetch error:', e); }
  }, [token]);

  const fetchAuditStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/audit-trail/stats`, { headers });
      if (res.ok) setAuditStats(await res.json());
    } catch (e) { console.error('Audit stats fetch error:', e); }
  }, [token]);

  const fetchRBAC = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/rbac-matrix`, { headers });
      if (res.ok) setRbacMatrix(await res.json());
    } catch (e) { console.error('RBAC fetch error:', e); }
  }, [token]);

  const fetchEncryption = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/encryption-evidence`, { headers });
      if (res.ok) setEncryptionEvidence(await res.json());
    } catch (e) { console.error('Encryption evidence fetch error:', e); }
  }, [token]);

  useEffect(() => {
    Promise.all([fetchSummary(), fetchAuditLogs(), fetchAuditStats(), fetchRBAC(), fetchEncryption(), fetchLatestReport(), fetchReportHistory()])
      .finally(() => setLoading(false));
  }, []);

  const handleKillSwitch = async (action) => {
    setKillSwitchLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/compliance/kill-switch/${action}`, {
        method: 'POST', headers, body: JSON.stringify({}),
      });
      if (res.ok) {
        await fetchSummary();
      }
    } catch (e) { console.error('Kill switch error:', e); }
    setKillSwitchLoading(false);
  };

  const handleToggle = async (endpoint, enabled) => {
    setKillSwitchLoading(true);
    try {
      await fetch(`${API_URL}/api/compliance/kill-switch/${endpoint}`, {
        method: 'POST', headers, body: JSON.stringify({ enabled }),
      });
      await fetchSummary();
    } catch (e) { console.error('Toggle error:', e); }
    setKillSwitchLoading(false);
  };

  const handleDataDeletion = async () => {
    if (!deleteTenantId || !deleteConfirm) return;
    try {
      const res = await fetch(`${API_URL}/api/compliance/data-deletion`, {
        method: 'POST', headers,
        body: JSON.stringify({ tenant_id: deleteTenantId, confirm: true }),
      });
      if (res.ok) setDeleteResult(await res.json());
    } catch (e) { console.error('Data deletion error:', e); }
  };

  const handleSnapshot = async () => {
    setSnapshotLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/compliance/evidence-snapshot`, {
        method: 'POST', headers, body: JSON.stringify({}),
      });
      if (res.ok) {
        await fetchSummary();
      }
    } catch (e) { console.error('Snapshot error:', e); }
    setSnapshotLoading(false);
  };

  const [reportLoading, setReportLoading] = useState(false);
  const [reportHistory, setReportHistory] = useState([]);
  const [latestReport, setLatestReport] = useState(null);

  const fetchReportHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/daily-report/history?limit=10`, { headers });
      if (res.ok) {
        const data = await res.json();
        setReportHistory(data.reports || []);
      }
    } catch (e) { console.error('Report history fetch error:', e); }
  }, [token]);

  const fetchLatestReport = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/compliance/daily-report/latest`, { headers });
      if (res.ok) setLatestReport(await res.json());
    } catch (e) { console.error('Latest report fetch error:', e); }
  }, [token]);

  const handleGenerateReport = async () => {
    setReportLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/compliance/daily-report/generate`, {
        method: 'POST', headers, body: JSON.stringify({}),
      });
      if (res.ok) {
        await fetchLatestReport();
        await fetchReportHistory();
        await fetchSummary();
      }
    } catch (e) { console.error('Generate report error:', e); }
    setReportLoading(false);
  };

  const ks = summary?.kill_switch || {};
  const controls = summary?.controls_status || {};

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Shield },
    { id: 'kill-switch', label: 'Kill Switch', icon: Power },
    { id: 'audit-trail', label: 'Audit Trail', icon: Eye },
    { id: 'rbac', label: 'Agent RBAC', icon: Users },
    { id: 'encryption', label: 'Encryption', icon: Lock },
    { id: 'auto-reports', label: 'Auto-Reports', icon: FileText },
    { id: 'data-deletion', label: 'Data Deletion', icon: Trash2 },
  ];

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center" data-testid="soc2-loading">
        <div className="text-center">
          <Shield className="size-10 mx-auto mb-3 animate-pulse" style={{ color: 'var(--aurem-accent)' }} />
          <p className="text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>Loading SOC 2 Compliance…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="soc2-compliance-dashboard">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <Shield className="size-6" style={{ color: 'var(--aurem-accent)' }} />
          <h1 className="text-xl font-bold tracking-wide" style={{ color: 'var(--aurem-heading)' }}>
            SOC 2 Compliance Center
          </h1>
        </div>
        <p className="text-xs ml-9" style={{ color: 'var(--aurem-body-secondary)' }}>
          Trust Services Criteria, Confidentiality, Integrity, Availability, Privacy, Security
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 overflow-x-auto pb-1">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`soc2-tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'text-white'
                  : 'hover:opacity-80'
              }`}
              style={{
                background: activeTab === tab.id ? 'var(--aurem-accent)' : 'var(--aurem-glass)',
                color: activeTab === tab.id ? 'white' : 'var(--aurem-body)',
              }}
            >
              <Icon className="size-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ═══ OVERVIEW TAB ═══ */}
      {activeTab === 'overview' && (
        <div className="space-y-4" data-testid="soc2-overview">
          {/* Status Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Audit Logs (24h)', value: summary?.audit_logs_24h ?? 0, color: '#FF6B00' },
              { label: 'Security Events', value: summary?.security_events_24h ?? 0, color: summary?.security_events_24h > 0 ? '#DC2626' : '#FF6B00' },
              { label: 'Evidence Snapshots', value: summary?.evidence_snapshots ?? 0, color: '#FF6B00' },
              { label: 'Security Audit', value: summary?.last_security_audit ? `${summary.last_security_audit.green}/10` : 'N/A', color: '#FF6B00' },
              { label: 'Daily Reports', value: summary?.total_daily_reports ?? 0, color: '#FF6B00' },
              { label: 'Last Report', value: summary?.last_daily_report?.status || 'None', color: summary?.last_daily_report?.status === 'GREEN' ? '#FF6B00' : '#FF6B00' },
              { label: 'HMAC Signing', value: controls.hmac_patch_signing ? 'Active' : 'Off', color: '#FF6B00' },
              { label: 'Auto-Scheduler', value: controls.daily_compliance_reports ? 'Active' : 'Off', color: '#FF6B00' },
            ].map((card, i) => (
              <div key={i} className="rounded-xl p-4" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
                <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>{card.label}</div>
                <div className="text-2xl font-bold" style={{ color: card.color }}>{card.value}</div>
              </div>
            ))}
          </div>

          {/* Controls Status */}
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>SOC 2 Controls Status</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {Object.entries(controls).map(([key, val]) => (
                <div key={key} className="flex items-center gap-2 text-xs p-2 rounded-lg" style={{ background: 'var(--aurem-card-bg)' }}>
                  {val ? <CheckCircle className="size-3.5 text-green-500" /> : <XCircle className="size-3.5 text-red-500" />}
                  <span style={{ color: 'var(--aurem-body)' }}>{key.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Take Snapshot */}
          <button
            onClick={handleSnapshot}
            disabled={snapshotLoading}
            data-testid="take-evidence-snapshot-btn"
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium text-white transition-all"
            style={{ background: 'var(--aurem-accent)' }}
          >
            <FileText className="size-3.5" />
            {snapshotLoading ? 'Taking Snapshot...' : 'Take Evidence Snapshot'}
          </button>
        </div>
      )}

      {/* ═══ KILL SWITCH TAB ═══ */}
      {activeTab === 'kill-switch' && (
        <div className="space-y-4" data-testid="soc2-kill-switch">
          {/* Emergency Kill Switch */}
          <div className="rounded-xl p-5 border-2" style={{ background: 'var(--aurem-glass)', borderColor: ks.maintenance_mode ? '#DC2626' : 'var(--aurem-border)' }}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: ks.maintenance_mode ? '#DC2626' : 'var(--aurem-heading)' }}>
                  <AlertTriangle className="size-4" />
                  Global Kill Switch
                </h3>
                <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Emergency shutdown of all autonomous systems
                </p>
              </div>
              <button
                onClick={() => handleKillSwitch(ks.maintenance_mode ? 'deactivate' : 'activate')}
                disabled={killSwitchLoading}
                data-testid="global-kill-switch-btn"
                className={`px-5 py-2.5 rounded-xl text-xs font-bold tracking-wider transition-all ${
                  ks.maintenance_mode ? 'bg-green-600 hover:bg-green-700 text-white' : 'bg-red-600 hover:bg-red-700 text-white'
                }`}
              >
                <Power className="size-4 inline mr-1.5" />
                {ks.maintenance_mode ? 'DEACTIVATE' : 'ACTIVATE'}
              </button>
            </div>

            {ks.activated_by && (
              <div className="text-[10px] px-3 py-1.5 rounded-lg mb-3" style={{ background: 'var(--aurem-card-bg)', color: 'var(--aurem-body-secondary)' }}>
                Last activated by: {ks.activated_by} at {ks.activated_at}
              </div>
            )}
          </div>

          {/* Individual Controls */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              {
                label: 'Live Patches',
                desc: 'Disable all pixel DOM injections globally',
                active: !ks.live_patches_disabled,
                toggle: () => handleToggle('patches', ks.live_patches_disabled),
                testId: 'toggle-live-patches',
              },
              {
                label: 'V2V Sessions',
                desc: 'Revoke all active voice sessions',
                active: !ks.v2v_sessions_revoked,
                toggle: () => handleKillSwitch('v2v'),
                testId: 'revoke-v2v-btn',
              },
              {
                label: 'Maintenance Mode',
                desc: 'Put entire system into maintenance',
                active: !ks.maintenance_mode,
                toggle: () => handleToggle('maintenance', ks.maintenance_mode),
                testId: 'toggle-maintenance',
              },
            ].map((ctrl, i) => (
              <div key={i} className="rounded-xl p-4" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>{ctrl.label}</span>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold ${ctrl.active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {ctrl.active ? 'ACTIVE' : 'DISABLED'}
                  </span>
                </div>
                <p className="text-[10px] mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>{ctrl.desc}</p>
                <button
                  onClick={ctrl.toggle}
                  disabled={killSwitchLoading}
                  data-testid={ctrl.testId}
                  className="w-full px-3 py-1.5 rounded-lg text-[10px] font-medium text-white transition-all"
                  style={{ background: ctrl.active ? '#DC2626' : '#FF6B00' }}
                >
                  {ctrl.active ? 'Disable' : 'Enable'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ AUDIT TRAIL TAB ═══ */}
      {activeTab === 'audit-trail' && (
        <div className="space-y-4" data-testid="soc2-audit-trail">
          {/* Stats */}
          {auditStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Total All Time', value: auditStats.total_all_time },
                { label: 'Last 24h', value: auditStats.total_24h },
                { label: 'Last 7 Days', value: auditStats.total_7d },
                { label: 'Security (24h)', value: auditStats.security_events_24h, color: auditStats.security_events_24h > 0 ? '#DC2626' : '#FF6B00' },
              ].map((s, i) => (
                <div key={i} className="rounded-xl p-3" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
                  <div className="text-[9px] uppercase tracking-widest" style={{ color: 'var(--aurem-body-secondary)' }}>{s.label}</div>
                  <div className="text-xl font-bold" style={{ color: s.color || 'var(--aurem-heading)' }}>{s.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Log Table */}
          <div className="rounded-xl overflow-hidden" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--aurem-border)' }}>
              <h3 className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Immutable Audit Log (Last 7 Days)</h3>
              <button onClick={() => { fetchAuditLogs(); fetchAuditStats(); }} data-testid="refresh-audit-logs-btn" className="p-1 rounded hover:opacity-70">
                <RefreshCw className="size-3.5" style={{ color: 'var(--aurem-body-secondary)' }} />
              </button>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              {auditLogs.length === 0 ? (
                <div className="p-6 text-center text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No audit logs found</div>
              ) : (
                auditLogs.map((log, i) => (
                  <div key={i} className="px-4 py-2 cursor-pointer hover:opacity-80 transition-all" style={{ borderBottom: '1px solid var(--aurem-border)' }}
                    onClick={() => setExpandedLog(expandedLog === i ? null : i)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`size-1.5 rounded-full ${log.success === false ? 'bg-red-500' : 'bg-green-500'}`} />
                        <span className="text-[10px] font-mono font-bold" style={{ color: 'var(--aurem-accent)' }}>{log.action}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: 'var(--aurem-card-bg)', color: 'var(--aurem-body-secondary)' }}>
                          {log.actor_type}:{log.actor_id?.substring(0, 20)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                          {log.timestamp ? new Date(log.timestamp).toLocaleString() : ''}
                        </span>
                        {expandedLog === i ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
                      </div>
                    </div>
                    {expandedLog === i && (
                      <div className="mt-2 p-2 rounded-lg text-[10px] font-mono" style={{ background: 'var(--aurem-card-bg)', color: 'var(--aurem-body-secondary)' }}>
                        <pre className="whitespace-pre-wrap">{JSON.stringify({
                          resource_type: log.resource_type,
                          resource_id: log.resource_id,
                          business_id: log.business_id,
                          details: log.details,
                          ip_address: log.ip_address,
                          user_agent: log.user_agent,
                        }, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ RBAC TAB ═══ */}
      {activeTab === 'rbac' && rbacMatrix && (
        <div className="space-y-4" data-testid="soc2-rbac">
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-1" style={{ color: 'var(--aurem-heading)' }}>{rbacMatrix.title}</h3>
            <p className="text-[10px] mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>{rbacMatrix.principle}</p>

            {/* Role descriptions */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-4">
              {Object.entries(rbacMatrix.roles || {}).map(([role, desc]) => (
                <div key={role} className="p-2 rounded-lg" style={{ background: 'var(--aurem-card-bg)' }}>
                  <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--aurem-accent)' }}>{role}</span>
                  <p className="text-[9px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{desc}</p>
                </div>
              ))}
            </div>

            {/* Permission Matrix Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--aurem-border)' }}>
                    <th className="text-left py-2 px-2 font-bold" style={{ color: 'var(--aurem-heading)' }}>Permission</th>
                    {Object.keys(rbacMatrix.matrix || {}).map(role => (
                      <th key={role} className="text-center py-2 px-2 font-bold uppercase" style={{ color: 'var(--aurem-accent)' }}>{role}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {['db_read', 'db_write', 'api_call_external', 'deploy_patch', 'access_credentials', 'modify_settings', 'trigger_scan', 'send_notification'].map(perm => (
                    <tr key={perm} style={{ borderBottom: '1px solid var(--aurem-border)' }}>
                      <td className="py-1.5 px-2 font-mono" style={{ color: 'var(--aurem-body)' }}>{perm}</td>
                      {Object.entries(rbacMatrix.matrix || {}).map(([role, perms]) => (
                        <td key={role} className="text-center py-1.5 px-2">
                          {perms.includes(perm) ? (
                            <CheckCircle className="size-3.5 text-green-500 mx-auto" />
                          ) : (
                            <XCircle className="size-3.5 text-red-400/40 mx-auto" />
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ═══ ENCRYPTION TAB ═══ */}
      {activeTab === 'encryption' && encryptionEvidence && (
        <div className="space-y-4" data-testid="soc2-encryption">
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>Encryption at Rest</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(encryptionEvidence.encryption_at_rest || {}).map(([k, v]) => (
                <div key={k} className="p-3 rounded-lg" style={{ background: 'var(--aurem-card-bg)' }}>
                  <span className="text-[9px] uppercase tracking-wider font-bold" style={{ color: 'var(--aurem-accent)' }}>{k}</span>
                  <p className="text-xs mt-1" style={{ color: 'var(--aurem-body)' }}>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>Encryption in Transit</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(encryptionEvidence.encryption_in_transit || {}).map(([k, v]) => (
                <div key={k} className="p-3 rounded-lg" style={{ background: 'var(--aurem-card-bg)' }}>
                  <span className="text-[9px] uppercase tracking-wider font-bold" style={{ color: 'var(--aurem-accent)' }}>{k}</span>
                  <p className="text-xs mt-1" style={{ color: 'var(--aurem-body)' }}>{String(v)}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--aurem-heading)' }}>Compliance Notes</h3>
            <ul className="space-y-1">
              {(encryptionEvidence.compliance_notes || []).map((note, i) => (
                <li key={i} className="flex items-start gap-2 text-xs" style={{ color: 'var(--aurem-body)' }}>
                  <CheckCircle className="size-3 text-green-500 mt-0.5 flex-shrink-0" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ═══ AUTO-REPORTS TAB ═══ */}
      {activeTab === 'auto-reports' && (
        <div className="space-y-4" data-testid="soc2-auto-reports">
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Daily Compliance Auto-Reports</h3>
                <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
                  Automated scheduler runs at midnight UTC. Includes security audit + evidence snapshot.
                </p>
              </div>
              <button
                onClick={handleGenerateReport}
                disabled={reportLoading}
                data-testid="generate-report-now-btn"
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium text-white transition-all"
                style={{ background: 'var(--aurem-accent)' }}
              >
                <Activity className="size-3.5" />
                {reportLoading ? 'Generating...' : 'Generate Now'}
              </button>
            </div>

            {/* Latest Report */}
            {latestReport && latestReport.report_id && (
              <div className="rounded-lg p-4 mb-4" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold" style={{ color: 'var(--aurem-heading)' }}>Latest Report</span>
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-bold ${
                    latestReport.status === 'GREEN' ? 'bg-green-100 text-green-700' :
                    latestReport.status === 'YELLOW' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {latestReport.status}
                  </span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[10px]">
                  <div>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>Report ID</span>
                    <div className="font-mono" style={{ color: 'var(--aurem-body)' }}>{latestReport.report_id}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>Generated</span>
                    <div style={{ color: 'var(--aurem-body)' }}>{new Date(latestReport.generated_at).toLocaleString()}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>Security Score</span>
                    <div className="font-bold" style={{ color: '#FF6B00' }}>{latestReport.security_audit?.score || 'N/A'}</div>
                  </div>
                  <div>
                    <span style={{ color: 'var(--aurem-body-secondary)' }}>Controls</span>
                    <div style={{ color: 'var(--aurem-body)' }}>
                      {latestReport.compliance_controls ? Object.values(latestReport.compliance_controls).filter(v => v === 'ACTIVE' || v === 'AVAILABLE').length : 0} Active
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Report History */}
            <h4 className="text-xs font-bold mb-2" style={{ color: 'var(--aurem-heading)' }}>Report History</h4>
            <div className="space-y-1">
              {reportHistory.length === 0 ? (
                <p className="text-xs p-3 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>No reports generated yet</p>
              ) : (
                reportHistory.map((r, i) => (
                  <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--aurem-card-bg)' }}>
                    <div className="flex items-center gap-2">
                      <span className={`size-2 rounded-full ${
                        r.status === 'GREEN' ? 'bg-green-500' : r.status === 'YELLOW' ? 'bg-yellow-500' : 'bg-red-500'
                      }`} />
                      <span className="text-[10px] font-mono" style={{ color: 'var(--aurem-body)' }}>{r.report_id}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-bold" style={{ color: '#FF6B00' }}>{r.security_audit?.score || 'N/A'}</span>
                      <span className="text-[9px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                        {new Date(r.generated_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ DATA DELETION TAB ═══ */}
      {activeTab === 'data-deletion' && (
        <div className="space-y-4" data-testid="soc2-data-deletion">
          <div className="rounded-xl p-5" style={{ background: 'var(--aurem-glass)', border: '1px solid var(--aurem-border)' }}>
            <h3 className="text-sm font-bold mb-1 flex items-center gap-2" style={{ color: 'var(--aurem-heading)' }}>
              <Trash2 className="size-4" />
              GDPR / PIPEDA, Right to Erasure
            </h3>
            <p className="text-[10px] mb-4" style={{ color: 'var(--aurem-body-secondary)' }}>
              Permanently delete all data for a specific tenant. Audit trail entries are retained for 2 years per compliance requirements.
            </p>

            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="text-[10px] font-bold block mb-1" style={{ color: 'var(--aurem-body)' }}>Tenant ID / Business ID</label>
                <input
                  type="text"
                  value={deleteTenantId}
                  onChange={(e) => setDeleteTenantId(e.target.value)}
                  data-testid="delete-tenant-id-input"
                  className="w-full px-3 py-2 rounded-lg text-xs"
                  style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)', color: 'var(--aurem-body)' }}
                  placeholder="e.g. biz_a572760d5b4ca0f6"
                />
              </div>
              <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--aurem-body)' }}>
                <input
                  type="checkbox"
                  checked={deleteConfirm}
                  onChange={(e) => setDeleteConfirm(e.target.checked)}
                  data-testid="delete-confirm-checkbox"
                  className="rounded"
                />
                I confirm this deletion
              </label>
              <button
                onClick={handleDataDeletion}
                disabled={!deleteTenantId || !deleteConfirm}
                data-testid="execute-data-deletion-btn"
                className="px-4 py-2 rounded-lg text-xs font-bold text-white transition-all disabled:opacity-50"
                style={{ background: '#DC2626' }}
              >
                Delete All Data
              </button>
            </div>

            {deleteResult && (
              <div className="mt-4 p-3 rounded-lg" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-border)' }}>
                <div className="text-xs font-bold mb-2" style={{ color: '#DC2626' }}>Deletion Complete</div>
                <pre className="text-[10px] font-mono whitespace-pre-wrap" style={{ color: 'var(--aurem-body)' }}>
                  {JSON.stringify(deleteResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SOC2ComplianceDashboard;
