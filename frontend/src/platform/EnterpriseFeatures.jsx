/**
 * Phase F: Enterprise Features — Team Management, Audit Trail, White-Label, Data Export
 */
import React, { useState, useEffect, useCallback , useMemo } from 'react';
import {
  Users, Shield, Eye, UserPlus, Trash2, ChevronDown,
  Download, Search, RefreshCw, CheckCircle, Clock, XCircle,
  Palette, Globe, Mail, FileText, AlertCircle, Edit3, X
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const ROLE_COLORS = {
  owner: '#D4AF37',
  admin: '#8B5CF6',
  manager: '#3b82f6',
  agent: '#FF6B00',
  viewer: '#888',
};

function Badge({ children, color }) {
  return (
    <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full" style={{ background: `${color}18`, color }}>{children}</span>
  );
}

function StatusDot({ status }) {
  const colors = { active: '#22c55e', invited: '#eab308', suspended: '#ef4444' };
  return <span className="inline-block w-2 h-2 rounded-full" style={{ background: colors[status] || '#888' }} />;
}

export default function EnterpriseFeatures({ token, user }) {
  const [tab, setTab] = useState('team');
  const [team, setTeam] = useState([]);
  const [roles, setRoles] = useState([]);
  const [audit, setAudit] = useState([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [whitelabel, setWhitelabel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'agent', first_name: '', last_name: '' });
  const [inviteResult, setInviteResult] = useState(null);
  const [wlForm, setWlForm] = useState({});
  const [wlSaving, setWlSaving] = useState(false);
  const [searchAudit, setSearchAudit] = useState('');

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);

  const fetchTeam = useCallback(async () => {
    try {
      const [teamRes, rolesRes] = await Promise.all([
        fetch(`${API}/api/enterprise/team`, { headers }),
        fetch(`${API}/api/enterprise/roles`, { headers }),
      ]);
      if (teamRes.ok) { const d = await teamRes.json(); setTeam(d.members || []); }
      if (rolesRes.ok) { const d = await rolesRes.json(); setRoles(d.roles || []); }
    } catch (e) { console.error(e); }
  }, [headers]);

  const fetchAudit = useCallback(async () => {
    try {
      const url = searchAudit ? `${API}/api/enterprise/audit?limit=50&action=${searchAudit}` : `${API}/api/enterprise/audit?limit=50`;
      const res = await fetch(url, { headers });
      if (res.ok) { const d = await res.json(); setAudit(d.logs || []); setAuditTotal(d.total || 0); }
    } catch (e) { console.error(e); }
  }, [searchAudit, headers]);

  const fetchWhitelabel = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/enterprise/whitelabel`, { headers });
      if (res.ok) { const d = await res.json(); setWhitelabel(d); setWlForm(d); }
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchTeam(), fetchAudit(), fetchWhitelabel()]).finally(() => setLoading(false));
  }, [fetchTeam, fetchAudit, fetchWhitelabel]);

  const handleInvite = async () => {
    if (!inviteForm.email) return;
    try {
      const res = await fetch(`${API}/api/enterprise/team/invite`, { method: 'POST', headers, body: JSON.stringify(inviteForm) });
      const d = await res.json();
      if (res.ok) {
        setInviteResult(d);
        setInviteForm({ email: '', role: 'agent', first_name: '', last_name: '' });
        fetchTeam();
        fetchAudit();
      } else {
        setInviteResult({ error: d.detail || 'Failed to invite' });
      }
    } catch (e) { setInviteResult({ error: e.message }); }
  };

  const handleRemove = async (memberId) => {
    if (!window.confirm('Remove this team member?')) return;
    try {
      await fetch(`${API}/api/enterprise/team/${memberId}`, { method: 'DELETE', headers });
      fetchTeam();
      fetchAudit();
    } catch (e) { console.error(e); }
  };

  const handleRoleChange = async (memberId, newRole) => {
    try {
      await fetch(`${API}/api/enterprise/team/${memberId}/role`, { method: 'PUT', headers, body: JSON.stringify({ role: newRole }) });
      fetchTeam();
      fetchAudit();
    } catch (e) { console.error(e); }
  };

  const handleWlSave = async () => {
    setWlSaving(true);
    try {
      await fetch(`${API}/api/enterprise/whitelabel`, { method: 'PUT', headers, body: JSON.stringify(wlForm) });
      fetchWhitelabel();
      fetchAudit();
    } catch (e) { console.error(e); }
    setWlSaving(false);
  };

  const handleExport = async (resource, format = 'json') => {
    try {
      const res = await fetch(`${API}/api/enterprise/export/${resource}?format=${format}`, { headers });
      if (format === 'csv') {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${resource}_export.csv`; a.click();
      } else {
        const d = await res.json();
        const blob = new Blob([JSON.stringify(d.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${resource}_export.json`; a.click();
      }
    } catch (e) { console.error(e); }
  };

  const tabs = [
    { id: 'team', label: 'Team', icon: Users },
    { id: 'audit', label: 'Audit Trail', icon: Eye },
    { id: 'whitelabel', label: 'White-Label', icon: Palette },
    { id: 'export', label: 'Data Export', icon: Download },
  ];

  return (
    <div className="flex-1 overflow-auto p-6 space-y-6" data-testid="enterprise-features">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--aurem-text)' }}>Enterprise</h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--aurem-text-secondary)' }}>Phase F — Team, audit, branding & compliance</p>
        </div>
        <button onClick={() => { fetchTeam(); fetchAudit(); fetchWhitelabel(); }} disabled={loading} className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all" style={{ background: '#FF6B0018', color: '#FF6B00' }} data-testid="refresh-enterprise">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(128,128,128,0.1)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} data-testid={`tab-${t.id}`}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-all ${tab === t.id ? 'shadow-sm' : ''}`}
            style={{ background: tab === t.id ? '#fff' : 'transparent', color: tab === t.id ? '#FF6B00' : '#888' }}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      {/* ═══ TEAM TAB ═══ */}
      {tab === 'team' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium" style={{ color: 'var(--aurem-text-secondary)' }}>{team.length} member{team.length !== 1 ? 's' : ''}</span>
            <button onClick={() => { setShowInvite(true); setInviteResult(null); }} className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white transition-all" style={{ background: '#FF6B00' }} data-testid="invite-member-btn">
              <UserPlus size={14} /> Invite Member
            </button>
          </div>

          {/* Invite Modal */}
          {showInvite && (
            <div className="aurem-glass-card p-5 rounded-2xl space-y-3" data-testid="invite-modal">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>Invite Team Member</h3>
                <button onClick={() => setShowInvite(false)}><X size={16} style={{ color: 'var(--aurem-text-secondary)' }} /></button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input placeholder="First Name" value={inviteForm.first_name} onChange={e => setInviteForm(p => ({ ...p, first_name: e.target.value }))} className="px-3 py-2 rounded-lg text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid="invite-first-name" />
                <input placeholder="Last Name" value={inviteForm.last_name} onChange={e => setInviteForm(p => ({ ...p, last_name: e.target.value }))} className="px-3 py-2 rounded-lg text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid="invite-last-name" />
              </div>
              <input placeholder="Email address" type="email" value={inviteForm.email} onChange={e => setInviteForm(p => ({ ...p, email: e.target.value }))} className="w-full px-3 py-2 rounded-lg text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid="invite-email" />
              <select value={inviteForm.role} onChange={e => setInviteForm(p => ({ ...p, role: e.target.value }))} className="w-full px-3 py-2 rounded-lg text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid="invite-role">
                {roles.filter(r => r.id !== 'owner').map(r => <option key={r.id} value={r.id}>{r.label} — {r.desc}</option>)}
              </select>
              <button onClick={handleInvite} className="w-full py-2.5 rounded-xl text-sm font-semibold text-white" style={{ background: '#FF6B00' }} data-testid="send-invite-btn">Send Invite</button>
              {inviteResult && (
                <div className={`text-xs p-2 rounded-lg ${inviteResult.error ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700'}`} data-testid="invite-result">
                  {inviteResult.error || `Invited ${inviteResult.email} — temp password: ${inviteResult.temp_password}`}
                </div>
              )}
            </div>
          )}

          {/* Team Table */}
          <div className="aurem-glass-card rounded-2xl overflow-hidden">
            <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
              {team.map(m => (
                <div key={m.id} className="px-5 py-3.5 flex items-center justify-between hover:bg-black/[0.02] transition-colors" data-testid={`team-member-${m.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: ROLE_COLORS[m.role] || '#888' }}>
                      {(m.first_name?.[0] || m.email?.[0] || '?').toUpperCase()}
                    </div>
                    <div>
                      <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>
                        {m.first_name || ''} {m.last_name || ''} {(!m.first_name && !m.last_name) ? m.email : ''}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{m.email}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusDot status={m.status} />
                    <Badge color={ROLE_COLORS[m.role]}>{m.role}</Badge>
                    {!m.is_owner && (
                      <div className="flex items-center gap-1">
                        <select value={m.role} onChange={e => handleRoleChange(m.id, e.target.value)} className="text-xs border rounded-lg px-1.5 py-1" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid={`role-select-${m.id}`}>
                          {roles.filter(r => r.id !== 'owner').map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                        </select>
                        <button onClick={() => handleRemove(m.id)} className="p-1.5 rounded-lg hover:bg-red-50 transition-colors" data-testid={`remove-member-${m.id}`}>
                          <Trash2 size={13} className="text-red-400" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══ AUDIT TRAIL TAB ═══ */}
      {tab === 'audit' && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-text-secondary)' }} />
              <input placeholder="Filter by action (e.g. team.invite, whitelabel)..." value={searchAudit} onChange={e => setSearchAudit(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchAudit()} className="w-full pl-9 pr-3 py-2 rounded-xl text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid="audit-search" />
            </div>
            <button onClick={fetchAudit} className="px-3 py-2 rounded-xl text-xs font-medium" style={{ background: '#FF6B0018', color: '#FF6B00' }} data-testid="audit-search-btn">Search</button>
            <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{auditTotal} entries</span>
          </div>
          <div className="aurem-glass-card rounded-2xl overflow-hidden">
            {audit.length === 0 ? (
              <div className="p-8 text-center">
                <Eye size={32} className="mx-auto mb-3" style={{ color: 'var(--aurem-text-secondary)' }} />
                <p className="text-sm" style={{ color: 'var(--aurem-text-secondary)' }}>No audit events yet</p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: 'rgba(128,128,128,0.1)' }}>
                {audit.map((log, i) => (
                  <div key={log.id || i} className="px-5 py-3 flex items-center justify-between hover:bg-black/[0.02] transition-colors" data-testid={`audit-entry-${i}`}>
                    <div>
                      <span className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{log.action}</span>
                      <span className="text-xs ml-2" style={{ color: 'var(--aurem-text-secondary)' }}>{log.resource}</span>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <span className="text-xs ml-2" style={{ color: 'var(--aurem-text-secondary)' }}>{JSON.stringify(log.details).slice(0, 60)}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono" style={{ color: 'var(--aurem-text-secondary)' }}>{log.user_id?.slice(0, 8)}</span>
                      <span className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{log.created_at?.slice(0, 16).replace('T', ' ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══ WHITE-LABEL TAB ═══ */}
      {tab === 'whitelabel' && (
        <div className="aurem-glass-card p-6 rounded-2xl space-y-5" data-testid="whitelabel-settings">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--aurem-text)' }}>Brand Customization</h3>
          <div className="grid grid-cols-2 gap-4">
            {[
              { key: 'brand_name', label: 'Brand Name', placeholder: 'AUREM' },
              { key: 'custom_domain', label: 'Custom Domain', placeholder: 'app.yourdomain.com' },
              { key: 'logo_url', label: 'Logo URL', placeholder: 'https://...' },
              { key: 'favicon_url', label: 'Favicon URL', placeholder: 'https://...' },
              { key: 'support_email', label: 'Support Email', placeholder: 'support@yourdomain.com' },
              { key: 'footer_text', label: 'Footer Text', placeholder: 'Powered by AUREM AI' },
            ].map(field => (
              <div key={field.key}>
                <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-text-secondary)' }}>{field.label}</label>
                <input value={wlForm[field.key] || ''} onChange={e => setWlForm(p => ({ ...p, [field.key]: e.target.value }))} placeholder={field.placeholder} className="w-full px-3 py-2 rounded-lg text-sm border" style={{ borderColor: 'rgba(128,128,128,0.2)' }} data-testid={`wl-${field.key}`} />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-text-secondary)' }}>Primary Color</label>
              <div className="flex items-center gap-2">
                <input type="color" value={wlForm.primary_color || '#FF6B00'} onChange={e => setWlForm(p => ({ ...p, primary_color: e.target.value }))} className="w-8 h-8 rounded cursor-pointer" data-testid="wl-primary-color" />
                <span className="text-xs font-mono" style={{ color: 'var(--aurem-text-secondary)' }}>{wlForm.primary_color || '#FF6B00'}</span>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block" style={{ color: 'var(--aurem-text-secondary)' }}>Accent Color</label>
              <div className="flex items-center gap-2">
                <input type="color" value={wlForm.accent_color || '#D4AF37'} onChange={e => setWlForm(p => ({ ...p, accent_color: e.target.value }))} className="w-8 h-8 rounded cursor-pointer" data-testid="wl-accent-color" />
                <span className="text-xs font-mono" style={{ color: 'var(--aurem-text-secondary)' }}>{wlForm.accent_color || '#D4AF37'}</span>
              </div>
            </div>
          </div>
          <button onClick={handleWlSave} disabled={wlSaving} className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white transition-all" style={{ background: '#FF6B00' }} data-testid="save-whitelabel-btn">
            {wlSaving ? 'Saving...' : 'Save Brand Settings'}
          </button>
        </div>
      )}

      {/* ═══ DATA EXPORT TAB ═══ */}
      {tab === 'export' && (
        <div className="space-y-4">
          <p className="text-sm" style={{ color: 'var(--aurem-text-secondary)' }}>Download your data in JSON or CSV format for compliance, migration, or analysis.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { resource: 'team', label: 'Team Members', icon: Users, desc: 'All team members and roles' },
              { resource: 'audit', label: 'Audit Trail', icon: Eye, desc: 'Full activity log' },
              { resource: 'invoices', label: 'Invoices', icon: FileText, desc: 'Payment history & invoices' },
              { resource: 'usage', label: 'Usage Data', icon: AlertCircle, desc: 'API calls, AI messages, storage' },
              { resource: 'payments', label: 'Payments', icon: Download, desc: 'Transaction records' },
            ].map(item => (
              <div key={item.resource} className="aurem-glass-card p-4 rounded-2xl flex items-center justify-between" data-testid={`export-${item.resource}`}>
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: '#FF6B0018' }}>
                    <item.icon size={16} style={{ color: '#FF6B00' }} />
                  </div>
                  <div>
                    <div className="text-sm font-medium" style={{ color: 'var(--aurem-text)' }}>{item.label}</div>
                    <div className="text-xs" style={{ color: 'var(--aurem-text-secondary)' }}>{item.desc}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleExport(item.resource, 'json')} className="px-3 py-1.5 rounded-lg text-xs font-medium border" style={{ borderColor: 'rgba(128,128,128,0.2)', color: 'var(--aurem-text-secondary)' }} data-testid={`export-${item.resource}-json`}>JSON</button>
                  <button onClick={() => handleExport(item.resource, 'csv')} className="px-3 py-1.5 rounded-lg text-xs font-medium text-white" style={{ background: '#FF6B00' }} data-testid={`export-${item.resource}-csv`}>CSV</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
