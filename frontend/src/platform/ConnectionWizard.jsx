/**
 * Connection Wizard — Per-Client Email + WhatsApp Integration Tab
 * Embedded within the Client Dashboard as the "Integrations" tab.
 * WhatsApp Hybrid: Meta Cloud API (primary) + WHAPI (fallback)
 */
import React, { useState, useEffect } from 'react';
import {
  Mail, MessageSquare, CheckCircle2, AlertTriangle, Loader2,
  Wifi, WifiOff, Shield, ArrowRight, RefreshCw, Copy, Eye, EyeOff,
  Zap, Lock, ToggleLeft, ToggleRight
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

export default function ConnectionWizard({ tenantId, token }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState(null);
  const [showPass, setShowPass] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);

  // WhatsApp Hybrid state
  const [waMode, setWaMode] = useState('meta'); // 'meta' | 'whapi'
  const [waStatus, setWaStatus] = useState(null);
  const [waConnecting, setWaConnecting] = useState(false);
  const [waTestResult, setWaTestResult] = useState(null);
  const [metaForm, setMetaForm] = useState({ phone_number_id: '', waba_id: '', access_token: '' });
  const [whapiForm, setWhapiForm] = useState({ whapi_token: '' });
  const [showMetaToken, setShowMetaToken] = useState(false);

  const [emailForm, setEmailForm] = useState({
    smtp_host: '', smtp_port: 587, smtp_user: '', smtp_pass: '',
    smtp_secure: true, from_name: '', from_email: '',
  });

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    fetchProfile();
    fetchWaStatus();
  }, [tenantId]);

  const fetchProfile = async () => {
    try {
      const res = await fetch(`${API}/api/integrations/status/${tenantId}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        if (data.email_config) {
          setEmailForm(prev => ({
            ...prev,
            smtp_host: data.email_config.smtp_host || '',
            smtp_port: data.email_config.smtp_port || 587,
            smtp_user: data.email_config.smtp_user || '',
            from_name: data.email_config.from_name || '',
            from_email: data.email_config.from_email || '',
            smtp_secure: data.email_config.smtp_secure !== false,
          }));
        }
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchWaStatus = async () => {
    try {
      const res = await fetch(`${API}/api/integrations/${tenantId}/whatsapp/status`, { headers });
      if (res.ok) {
        const data = await res.json();
        setWaStatus(data);
        if (data.mode === 'meta_cloud') setWaMode('meta');
        else if (data.mode === 'whapi') setWaMode('whapi');
      }
    } catch (e) { console.error(e); }
  };

  const saveEmail = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/integrations/email/configure/${tenantId}`, {
        method: 'POST', headers, body: JSON.stringify(emailForm),
      });
      await fetchProfile();
    } catch (e) { console.error(e); }
    setSaving(false);
  };

  const testEmail = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API}/api/integrations/email/test/${tenantId}`, {
        method: 'POST', headers,
      });
      const data = await res.json();
      setTestResult(data);
      if (data.success) await fetchProfile();
    } catch (e) { setTestResult({ success: false, error: 'Connection failed' }); }
    setTesting(false);
  };

  const connectMeta = async () => {
    setWaConnecting(true);
    setWaTestResult(null);
    try {
      const res = await fetch(`${API}/api/integrations/${tenantId}/whatsapp/connect-meta`, {
        method: 'POST', headers, body: JSON.stringify(metaForm),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setWaTestResult({ success: true, message: `Connected! ${data.phone_display_name || 'Meta Cloud API active'}` });
        await fetchWaStatus();
        await fetchProfile();
      } else {
        setWaTestResult({ success: false, error: data.detail || data.error || 'Connection failed' });
      }
    } catch (e) { setWaTestResult({ success: false, error: 'Request failed' }); }
    setWaConnecting(false);
  };

  const connectWhapi = async () => {
    setWaConnecting(true);
    setWaTestResult(null);
    try {
      const res = await fetch(`${API}/api/integrations/${tenantId}/whatsapp/connect-whapi`, {
        method: 'POST', headers, body: JSON.stringify(whapiForm),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setWaTestResult({ success: true, message: `Connected! Phone: ${data.phone || 'WHAPI active'}` });
        await fetchWaStatus();
        await fetchProfile();
      } else {
        setWaTestResult({ success: false, error: data.detail || data.error || 'Connection failed' });
      }
    } catch (e) { setWaTestResult({ success: false, error: 'Request failed' }); }
    setWaConnecting(false);
  };

  const copyToken = () => {
    if (profile?.activation_token) {
      navigator.clipboard.writeText(`${window.location.origin}/activate/${profile.activation_token}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12" data-testid="wizard-loading">
        <Loader2 className="animate-spin" size={24} style={{ color: '#D4AF37' }} />
        <span className="ml-3 text-sm" style={{ color: 'var(--aurem-body-secondary)' }}>Loading integrations…</span>
      </div>
    );
  }

  if (!profile || profile.status === 'not_provisioned') {
    return (
      <div className="text-center p-8 rounded-2xl" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }} data-testid="wizard-not-provisioned">
        <Shield size={40} className="mx-auto mb-4" style={{ color: '#5A5468' }} />
        <p className="text-sm font-semibold" style={{ color: 'var(--aurem-heading)' }}>Integration Not Set Up</p>
        <p className="text-xs mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>
          Contact your admin to provision your integration profile.
        </p>
      </div>
    );
  }

  const ec = profile.email_config || {};
  const waConnected = waStatus?.connected || false;
  const waCurrentMode = waStatus?.mode || 'not_connected';

  return (
    <div className="space-y-4" data-testid="connection-wizard">
      {/* Instance ID + Status */}
      <div className="rounded-2xl p-4" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs font-bold tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>SOVEREIGN INSTANCE</p>
            <p className="text-sm font-mono font-bold mt-1" style={{ color: '#D4AF37' }}>{profile.instance_id}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="size-2 rounded-full" style={{
              background: profile.status === 'active' ? '#4ADE80' :
                profile.status === 'email_active' ? '#D4AF37' : '#64C8FF',
              boxShadow: profile.status === 'active' ? '0 0 8px rgba(74,222,128,0.5)' : 'none',
            }} />
            <span className="text-xs font-bold uppercase tracking-wide" style={{
              color: profile.status === 'active' ? '#4ADE80' :
                profile.status === 'email_active' ? '#D4AF37' : '#64C8FF',
            }}>
              {profile.status === 'active' ? 'Fully Connected' :
               profile.status === 'email_active' ? 'Email Active' :
               'Pending Activation'}
            </span>
          </div>
        </div>
        {profile.activation_token && (
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Activation Link:</span>
            <button onClick={copyToken} className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors"
              style={{ background: 'rgba(212,175,55,0.08)', color: '#D4AF37', border: '1px solid rgba(212,175,55,0.2)' }}
              data-testid="copy-activation-link">
              <Copy size={10} />
              {copied ? 'Copied!' : 'Copy Link'}
            </button>
          </div>
        )}
      </div>

      {/* Email Integration Card */}
      <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--aurem-card-bg)', border: ec.verified ? '1px solid rgba(74,222,128,0.2)' : '1px solid var(--aurem-card-border)' }}
        data-testid="email-integration-card">
        <button
          onClick={() => setActiveSection(activeSection === 'email' ? null : 'email')}
          className="w-full p-4 flex items-center justify-between text-left"
        >
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center"
              style={{ background: ec.verified ? 'rgba(74,222,128,0.12)' : 'rgba(212,175,55,0.08)' }}>
              <Mail size={20} style={{ color: ec.verified ? '#4ADE80' : '#D4AF37' }} />
            </div>
            <div>
              <p className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>Email (SMTP)</p>
              <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                {ec.verified ? `Connected via ${ec.smtp_host}` : 'Not configured — add your SMTP details'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {ec.verified ? <CheckCircle2 size={16} style={{ color: '#4ADE80' }} /> : <ArrowRight size={16} style={{ color: '#5A5468' }} />}
          </div>
        </button>

        {activeSection === 'email' && (
          <div className="px-4 pb-4 space-y-3" data-testid="email-form">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>SMTP Host</label>
                <input type="text" value={emailForm.smtp_host} onChange={e => setEmailForm(f => ({ ...f, smtp_host: e.target.value }))}
                  placeholder="smtp.gmail.com" data-testid="smtp-host-input"
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Port</label>
                <input type="number" value={emailForm.smtp_port} onChange={e => setEmailForm(f => ({ ...f, smtp_port: parseInt(e.target.value) || 587 }))}
                  data-testid="smtp-port-input"
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Username / Email</label>
              <input type="email" value={emailForm.smtp_user} onChange={e => setEmailForm(f => ({ ...f, smtp_user: e.target.value }))}
                placeholder="you@company.com" data-testid="smtp-user-input"
                className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
              />
            </div>
            <div className="relative">
              <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>App Password</label>
              <input type={showPass ? 'text' : 'password'} value={emailForm.smtp_pass} onChange={e => setEmailForm(f => ({ ...f, smtp_pass: e.target.value }))}
                placeholder="App-specific password" data-testid="smtp-pass-input"
                className="w-full px-3 py-2 rounded-lg text-xs outline-none pr-8"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
              />
              <button onClick={() => setShowPass(!showPass)} className="absolute right-2 top-6" style={{ color: '#5A5468' }}>
                {showPass ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>From Name</label>
                <input type="text" value={emailForm.from_name} onChange={e => setEmailForm(f => ({ ...f, from_name: e.target.value }))}
                  placeholder="Your Business" data-testid="from-name-input"
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                />
              </div>
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>From Email</label>
                <input type="email" value={emailForm.from_email} onChange={e => setEmailForm(f => ({ ...f, from_email: e.target.value }))}
                  placeholder="noreply@company.com" data-testid="from-email-input"
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                />
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button onClick={saveEmail} disabled={saving} data-testid="save-email-btn"
                className="flex-1 py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all"
                style={{ background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507', opacity: saving ? 0.6 : 1 }}>
                {saving ? 'Saving...' : 'Save Configuration'}
              </button>
              <button onClick={testEmail} disabled={testing || !emailForm.smtp_host} data-testid="test-email-btn"
                className="px-4 py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all flex items-center gap-1.5"
                style={{ background: 'rgba(74,222,128,0.08)', color: '#4ADE80', border: '1px solid rgba(74,222,128,0.2)', opacity: testing ? 0.6 : 1 }}>
                {testing ? <Loader2 size={12} className="animate-spin" /> : <Wifi size={12} />}
                {testing ? 'Testing...' : 'Test'}
              </button>
            </div>

            {testResult && (
              <div className="flex items-center gap-2 p-3 rounded-xl text-xs" data-testid="test-result"
                style={{
                  background: testResult.success ? 'rgba(74,222,128,0.08)' : 'rgba(239,68,68,0.08)',
                  border: testResult.success ? '1px solid rgba(74,222,128,0.2)' : '1px solid rgba(239,68,68,0.2)',
                  color: testResult.success ? '#4ADE80' : '#EF4444',
                }}>
                {testResult.success ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                {testResult.success ? testResult.message : testResult.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* WhatsApp Hybrid Integration Card */}
      <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--aurem-card-bg)', border: waConnected ? '1px solid rgba(74,222,128,0.2)' : '1px solid var(--aurem-card-border)' }}
        data-testid="whatsapp-integration-card">
        <button
          onClick={() => setActiveSection(activeSection === 'whatsapp' ? null : 'whatsapp')}
          className="w-full p-4 flex items-center justify-between text-left"
        >
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl flex items-center justify-center"
              style={{ background: waConnected ? 'rgba(74,222,128,0.12)' : 'rgba(74,222,128,0.06)' }}>
              <MessageSquare size={20} style={{ color: waConnected ? '#4ADE80' : '#5A5468' }} />
            </div>
            <div>
              <p className="text-sm font-bold" style={{ color: 'var(--aurem-heading)' }}>WhatsApp</p>
              <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
                {waConnected && waCurrentMode === 'meta_cloud' ? 'Permanent (Meta Cloud API)' :
                 waConnected && waCurrentMode === 'whapi' ? `Session Active (WHAPI) — ${waStatus?.phone_number || ''}` :
                 'Not connected — choose a connection method'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {waConnected ? (
              <span className="px-2 py-0.5 rounded-full text-[9px] font-bold"
                style={{
                  background: waCurrentMode === 'meta_cloud' ? 'rgba(74,222,128,0.12)' : 'rgba(245,158,11,0.12)',
                  color: waCurrentMode === 'meta_cloud' ? '#4ADE80' : '#f59e0b',
                }}>
                {waCurrentMode === 'meta_cloud' ? 'Permanent' : 'Session'}
              </span>
            ) : <ArrowRight size={16} style={{ color: '#5A5468' }} />}
          </div>
        </button>

        {activeSection === 'whatsapp' && (
          <div className="px-4 pb-4 space-y-3" data-testid="whatsapp-setup">
            {/* Mode Toggle */}
            <div className="flex rounded-xl overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
              <button
                onClick={() => { setWaMode('meta'); setWaTestResult(null); }}
                className="flex-1 py-2.5 text-xs font-bold tracking-wide flex items-center justify-center gap-1.5 transition-all"
                style={{
                  background: waMode === 'meta' ? 'rgba(74,222,128,0.12)' : 'transparent',
                  color: waMode === 'meta' ? '#4ADE80' : 'var(--aurem-body-secondary)',
                }}
                data-testid="wa-mode-meta-btn"
              >
                <Lock size={12} /> Permanent (Meta API)
              </button>
              <button
                onClick={() => { setWaMode('whapi'); setWaTestResult(null); }}
                className="flex-1 py-2.5 text-xs font-bold tracking-wide flex items-center justify-center gap-1.5 transition-all"
                style={{
                  background: waMode === 'whapi' ? 'rgba(245,158,11,0.12)' : 'transparent',
                  color: waMode === 'whapi' ? '#f59e0b' : 'var(--aurem-body-secondary)',
                }}
                data-testid="wa-mode-whapi-btn"
              >
                <Zap size={12} /> Quick Start (WHAPI)
              </button>
            </div>

            {/* Meta Cloud API Form */}
            {waMode === 'meta' && (
              <div className="space-y-3" data-testid="meta-form">
                <div className="p-3 rounded-xl text-[10px] flex items-start gap-2"
                  style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.15)', color: '#4ADE80' }}>
                  <Lock size={12} className="flex-shrink-0 mt-0.5" />
                  <span>Meta Cloud API, Never expires. Requires a Meta Business Account with WhatsApp API access.</span>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Phone Number ID</label>
                  <input type="text" value={metaForm.phone_number_id} onChange={e => setMetaForm(f => ({ ...f, phone_number_id: e.target.value }))}
                    placeholder="e.g. 123456789012345" data-testid="meta-phone-id-input"
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Business Account ID (WABA ID)</label>
                  <input type="text" value={metaForm.waba_id} onChange={e => setMetaForm(f => ({ ...f, waba_id: e.target.value }))}
                    placeholder="e.g. 987654321098765" data-testid="meta-waba-id-input"
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                  />
                </div>
                <div className="relative">
                  <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>Access Token</label>
                  <input type={showMetaToken ? 'text' : 'password'} value={metaForm.access_token} onChange={e => setMetaForm(f => ({ ...f, access_token: e.target.value }))}
                    placeholder="Permanent access token" data-testid="meta-access-token-input"
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none pr-8"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                  />
                  <button onClick={() => setShowMetaToken(!showMetaToken)} className="absolute right-2 top-6" style={{ color: '#5A5468' }}>
                    {showMetaToken ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <button onClick={connectMeta} disabled={waConnecting || !metaForm.phone_number_id || !metaForm.access_token} data-testid="connect-meta-btn"
                  className="w-full py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all flex items-center justify-center gap-1.5"
                  style={{ background: 'linear-gradient(135deg, #4ADE80, #16a34a)', color: '#050507', opacity: (waConnecting || !metaForm.phone_number_id) ? 0.5 : 1 }}>
                  {waConnecting ? <Loader2 size={14} className="animate-spin" /> : <Lock size={14} />}
                  {waConnecting ? 'Verifying...' : 'Connect Meta Cloud API'}
                </button>
              </div>
            )}

            {/* WHAPI Form */}
            {waMode === 'whapi' && (
              <div className="space-y-3" data-testid="whapi-form">
                <div className="p-3 rounded-xl text-[10px] flex items-start gap-2"
                  style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)', color: '#f59e0b' }}>
                  <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
                  <span>Session-based, may expire if your phone restarts. Upgrade to Meta API anytime for permanent connection.</span>
                </div>
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: 'var(--aurem-body-secondary)' }}>WHAPI Token</label>
                  <input type="password" value={whapiForm.whapi_token} onChange={e => setWhapiForm({ whapi_token: e.target.value })}
                    placeholder="Paste your WHAPI API token" data-testid="whapi-token-input"
                    className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-heading)' }}
                  />
                </div>
                <button onClick={connectWhapi} disabled={waConnecting || !whapiForm.whapi_token} data-testid="connect-whapi-btn"
                  className="w-full py-2.5 rounded-xl text-xs font-bold tracking-wide transition-all flex items-center justify-center gap-1.5"
                  style={{ background: 'linear-gradient(135deg, #f59e0b, #b45309)', color: '#050507', opacity: (waConnecting || !whapiForm.whapi_token) ? 0.5 : 1 }}>
                  {waConnecting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                  {waConnecting ? 'Verifying...' : 'Connect WHAPI'}
                </button>
              </div>
            )}

            {/* Connection Result */}
            {waTestResult && (
              <div className="flex items-center gap-2 p-3 rounded-xl text-xs" data-testid="wa-test-result"
                style={{
                  background: waTestResult.success ? 'rgba(74,222,128,0.08)' : 'rgba(239,68,68,0.08)',
                  border: waTestResult.success ? '1px solid rgba(74,222,128,0.2)' : '1px solid rgba(239,68,68,0.2)',
                  color: waTestResult.success ? '#4ADE80' : '#EF4444',
                }}>
                {waTestResult.success ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                {waTestResult.success ? waTestResult.message : waTestResult.error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Usage Stats */}
      {(profile.emails_sent > 0 || profile.whatsapp_sent > 0 || (waStatus?.messages_total || 0) > 0) && (
        <div className="rounded-2xl p-4" style={{ background: 'var(--aurem-card-bg)', border: '1px solid var(--aurem-card-border)' }}
          data-testid="usage-stats">
          <p className="text-[10px] font-bold uppercase tracking-wider mb-3" style={{ color: 'var(--aurem-body-secondary)' }}>USAGE</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xl font-black" style={{ color: '#D4AF37' }}>{profile.emails_sent || 0}</p>
              <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Emails Sent</p>
            </div>
            <div>
              <p className="text-xl font-black" style={{ color: '#4ADE80' }}>{waStatus?.messages_total || profile.whatsapp_sent || 0}</p>
              <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>WhatsApp Sent</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
