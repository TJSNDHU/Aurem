/**
 * AUREM Settings Page
 * Account settings, security, notifications, and team management
 * Fully theme-aware using CSS variables
 */
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Settings, User, Shield, Bell, Users, Key, Lock, Mail,
  Save, Check, X, ChevronRight, Eye, EyeOff, RefreshCw,
  Smartphone, Globe, Moon, Sun, Palette, AlertCircle, LogOut,
  Plug, Zap, Database, Server, Activity, Copy, QrCode, Fingerprint,
  Linkedin
} from 'lucide-react';
import ApiKeysSettingsInline from './ApiKeysSettings';
import { getPlatformUser, setPlatformUser } from '../utils/secureTokenStore';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

export default function SettingsPage({ token, user }) {
  const [activeTab, setActiveTab] = useState('profile');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [integrations, setIntegrations] = useState([]);

  const [profile, setProfile] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    company: user?.company || '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  });

  const [security, setSecurity] = useState({
    current_password: '', new_password: '', confirm_password: '',
    two_factor_enabled: false, biometric_enabled: false
  });

  const [notifications, setNotifications] = useState({
    email_alerts: true, push_notifications: true, weekly_digest: true,
    security_alerts: true, marketing: false, deal_updates: true, agent_reports: true
  });

  // ── SHADOW-SAVING: localStorage + DB buffer on every change ──
  const shadowSave = useCallback((form, data) => {
    // 1. localStorage (instant)
    try { localStorage.setItem(`aurem_buffer_${form}`, JSON.stringify(data)); } catch {}
    // 2. DB buffer (async, fire-and-forget)
    if (token) {
      fetch(`${API_URL}/api/settings/buffer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ form, data }),
      }).catch(() => {});
    }
  }, [token]);
  useEffect(() => { shadowSave('profile', profile); }, [profile, shadowSave]);

  // Phone self-cleaning: strip dashes/spaces, add +1 for 10-digit
  const cleanPhone = (raw) => {
    if (!raw) return raw;
    const digits = raw.replace(/[^\d+]/g, '');
    if (!digits) return raw;
    if (digits.startsWith('+')) return digits;
    if (digits.length === 10) return `+1${digits}`;
    if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`;
    return digits;
  };

  const handleProfileChange = (field, value) => {
    setProfile(prev => ({ ...prev, [field]: value }));
  };

  const handlePhoneBlur = () => {
    if (profile.phone) {
      setProfile(prev => ({ ...prev, phone: cleanPhone(prev.phone) }));
    }
  };

  // Load saved profile from API, with buffer recovery fallback
  useEffect(() => {
    if (!token) return;
    fetch(`${API_URL}/api/settings/profile`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data) {
          setProfile(prev => ({
            ...prev,
            first_name: data.first_name || prev.first_name,
            last_name: data.last_name || prev.last_name,
            email: data.email || prev.email,
            phone: data.phone || prev.phone,
            company: data.company || prev.company,
            timezone: data.timezone || prev.timezone
          }));
        }
      })
      .catch(() => {
        // Recover from localStorage buffer
        try {
          const buffered = localStorage.getItem('aurem_buffer_profile');
          if (buffered) setProfile(prev => ({ ...prev, ...JSON.parse(buffered) }));
        } catch {}
      });
  }, [token]);
  const retryRef = React.useRef(null);

  const handleSaveProfile = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch(`${API_URL}/api/settings/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(profile)
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        const storedUser = getPlatformUser() || {};
        setPlatformUser({ ...storedUser, ...profile });
        // Clear buffer on success
        try { localStorage.removeItem('aurem_buffer_profile'); } catch {}
        if (retryRef.current) { clearInterval(retryRef.current); retryRef.current = null; }
      } else {
        throw new Error('Save returned non-OK status');
      }
    } catch (err) {
      console.error('Save failed:', err);
      setSaveError('Save failed. ORA will retry automatically...');
      // Start retry every 10s from buffer
      if (!retryRef.current) {
        retryRef.current = setInterval(async () => {
          try {
            const buffered = localStorage.getItem('aurem_buffer_profile');
            const data = buffered ? JSON.parse(buffered) : profile;
            const r = await fetch(`${API_URL}/api/settings/profile`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
              body: JSON.stringify(data)
            });
            if (r.ok) {
              setSaveError(null); setSaved(true); setTimeout(() => setSaved(false), 3000);
              try { localStorage.removeItem('aurem_buffer_profile'); } catch {}
              clearInterval(retryRef.current); retryRef.current = null;
            }
          } catch {}
        }, 10000);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (security.new_password !== security.confirm_password) return;
    if (security.new_password.length < 6) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/settings/password`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ current_password: security.current_password, new_password: security.new_password })
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        setSecurity({ ...security, current_password: '', new_password: '', confirm_password: '' });
      }
    } catch (err) {
      console.error('Password change failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_URL}/api/settings/notifications`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(notifications)
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      }
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setSaving(false);
    }
  };

  const fetchIntegrations = useCallback(async () => {
    const results = [];
    const checks = [
      { name: 'Stripe Payments', endpoint: '/api/aurem-billing/stripe-status', icon: Zap, category: 'payments' },
      { name: 'Gmail Channel', endpoint: `/api/oauth/gmail/status/${user?.id || 'default'}`, icon: Mail, category: 'communication' },
    ];
    for (const check of checks) {
      try {
        const res = await fetch(`${API_URL}${check.endpoint}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        const mode = data.mode || (data.connected ? 'live' : data.status === 'not_configured' ? 'not_configured' : 'mock');
        results.push({ ...check, mode, message: data.message || '' });
      } catch {
        results.push({ ...check, mode: 'unavailable', message: 'Service offline' });
      }
    }
    setIntegrations(results);
  }, [user, token]);

  useEffect(() => {
    if (activeTab === 'integrations') fetchIntegrations();
  }, [activeTab, fetchIntegrations]);

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'business-id', label: 'Business ID', icon: Fingerprint },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'api-keys', label: 'API Keys', icon: Key },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'integrations', label: 'Integrations', icon: Plug },
    { id: 'linkedin', label: 'LinkedIn', icon: Linkedin },
    { id: 'infrastructure', label: 'Infrastructure', icon: Server },
    { id: 'team', label: 'Team', icon: Users },
  ];

  const passwordsMatch = security.new_password === security.confirm_password;
  const passwordValid = security.new_password.length >= 6;

  const inputCls = "w-full px-3 py-2.5 rounded-lg text-xs outline-none transition-colors";

  return (
    <div className="flex-1 overflow-auto p-6" data-testid="settings-page"
      style={{ background: 'transparent' }}>
      <div className="max-w-5xl mx-auto">
        <div className="mb-8">
          <h1 className="text-xl font-semibold tracking-wider mb-1" style={{ color: '#D4AF37' }}>Settings</h1>
          <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Manage your account, security, and preferences</p>
        </div>

        <div className="flex gap-6">
          {/* Tab Navigation */}
          <div className="w-48 flex-shrink-0">
            <nav className="space-y-1">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  data-testid={`settings-tab-${tab.id}`}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-all ${
                    activeTab === tab.id ? 'border border-[#D4AF37]/30' : ''
                  }`}
                  style={{
                    background: activeTab === tab.id ? 'rgba(212,175,55,0.1)' : 'transparent',
                    color: activeTab === tab.id ? '#D4AF37' : 'var(--aurem-body-secondary)',
                  }}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Content */}
          <div className="flex-1">
            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-profile">
                <h2 className="text-sm font-medium mb-6" style={{ color: 'var(--aurem-heading)' }}>Profile Information</h2>
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>FIRST NAME</label>
                      <input
                        type="text" value={profile.first_name}
                        onChange={(e) => setProfile({ ...profile, first_name: e.target.value })}
                        data-testid="settings-first-name"
                        className={inputCls}
                        style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>LAST NAME</label>
                      <input
                        type="text" value={profile.last_name}
                        onChange={(e) => setProfile({ ...profile, last_name: e.target.value })}
                        data-testid="settings-last-name"
                        className={inputCls}
                        style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>EMAIL</label>
                    <input
                      type="email" value={profile.email}
                      onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                      data-testid="settings-email"
                      className={inputCls}
                      style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>PHONE</label>
                    <input
                      type="tel" value={profile.phone}
                      onChange={(e) => handleProfileChange('phone', e.target.value)}
                      onBlur={handlePhoneBlur}
                      placeholder="+1 (555) 123-4567"
                      data-testid="settings-phone"
                      className={inputCls}
                      style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>COMPANY</label>
                    <input
                      type="text" value={profile.company}
                      onChange={(e) => setProfile({ ...profile, company: e.target.value })}
                      placeholder="Your company name"
                      data-testid="settings-company"
                      className={inputCls}
                      style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>TIMEZONE</label>
                    <select
                      value={profile.timezone}
                      onChange={(e) => setProfile({ ...profile, timezone: e.target.value })}
                      data-testid="settings-timezone"
                      className={inputCls}
                      style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                    >
                      <option value="America/Toronto">Eastern Time (ET)</option>
                      <option value="America/Chicago">Central Time (CT)</option>
                      <option value="America/Denver">Mountain Time (MT)</option>
                      <option value="America/Los_Angeles">Pacific Time (PT)</option>
                      <option value="Europe/London">GMT (London)</option>
                      <option value="Europe/Paris">CET (Paris)</option>
                      <option value="Asia/Tokyo">JST (Tokyo)</option>
                      <option value="Asia/Dubai">GST (Dubai)</option>
                      <option value="Asia/Kolkata">IST (India)</option>
                    </select>
                  </div>
                </div>

                <div className="mt-6 pt-5 flex items-center justify-end gap-3" style={{ borderTop: '1px solid var(--aurem-divider)' }}>
                  {saved && (
                    <span className="flex items-center gap-1.5 text-[11px] text-[#4ade80]">
                      <Check className="w-3.5 h-3.5" /> Saved successfully
                    </span>
                  )}
                  {saveError && (
                    <span className="flex items-center gap-1.5 text-[10px] px-3 py-1.5 rounded-lg"
                      style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
                      data-testid="save-error-banner">
                      <RefreshCw className="w-3 h-3 animate-spin" /> {saveError}
                    </span>
                  )}
                  <button
                    onClick={handleSaveProfile} disabled={saving}
                    data-testid="save-profile-btn"
                    className="flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </div>
            )}

            {/* Business ID Tab */}
            {activeTab === 'business-id' && <BusinessIdTab token={token} />}

            {/* Security Tab */}
            {activeTab === 'security' && (
              <div className="space-y-6" data-testid="settings-security">
                <div className="aurem-glass-card rounded-xl p-6">
                  <h2 className="text-sm font-medium mb-6" style={{ color: 'var(--aurem-heading)' }}>Change Password</h2>
                  <div className="space-y-4 max-w-md">
                    <div>
                      <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>CURRENT PASSWORD</label>
                      <div className="relative">
                        <input
                          type={showCurrentPassword ? 'text' : 'password'}
                          value={security.current_password}
                          onChange={(e) => setSecurity({ ...security, current_password: e.target.value })}
                          data-testid="current-password-input"
                          className={inputCls}
                          style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)', paddingRight: '2.5rem' }}
                        />
                        <button onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-body-secondary)' }}>
                          {showCurrentPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>NEW PASSWORD</label>
                      <div className="relative">
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          value={security.new_password}
                          onChange={(e) => setSecurity({ ...security, new_password: e.target.value })}
                          data-testid="new-password-input"
                          className={inputCls}
                          style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)', paddingRight: '2.5rem' }}
                        />
                        <button onClick={() => setShowNewPassword(!showNewPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--aurem-body-secondary)' }}>
                          {showNewPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      {security.new_password && !passwordValid && (
                        <p className="text-[10px] text-[#ef4444] mt-1">Password must be at least 6 characters</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>CONFIRM PASSWORD</label>
                      <input
                        type="password" value={security.confirm_password}
                        onChange={(e) => setSecurity({ ...security, confirm_password: e.target.value })}
                        data-testid="confirm-password-input"
                        className={inputCls}
                        style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
                      />
                      {security.confirm_password && !passwordsMatch && (
                        <p className="text-[10px] text-[#ef4444] mt-1">Passwords do not match</p>
                      )}
                    </div>
                    <button
                      onClick={handleChangePassword}
                      disabled={!security.current_password || !passwordValid || !passwordsMatch || saving}
                      data-testid="change-password-btn"
                      className="flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      <Lock className="w-3.5 h-3.5" />
                      {saving ? 'Updating...' : 'Update Password'}
                    </button>
                  </div>
                </div>

                <div className="aurem-glass-card rounded-xl p-6">
                  <h2 className="text-sm font-medium mb-6" style={{ color: 'var(--aurem-heading)' }}>Security Options</h2>
                  <div className="space-y-4">
                    {[
                      { key: 'two_factor_enabled', label: 'Two-Factor Authentication', desc: 'Require a code from your authenticator app', icon: Key },
                      { key: 'biometric_enabled', label: 'Biometric Login', desc: 'Use fingerprint or Face ID to sign in', icon: Smartphone },
                    ].map(opt => (
                      <div key={opt.key} className="flex items-center justify-between p-4 rounded-lg" style={{ background: 'var(--aurem-surface)' }}>
                        <div className="flex items-center gap-3">
                          <opt.icon className="w-4 h-4 text-[#D4AF37]" />
                          <div>
                            <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{opt.label}</p>
                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{opt.desc}</p>
                          </div>
                        </div>
                        <button
                          onClick={() => setSecurity({ ...security, [opt.key]: !security[opt.key] })}
                          data-testid={`toggle-${opt.key}`}
                          className={`w-10 h-5 rounded-full transition-colors relative ${security[opt.key] ? 'bg-[#D4AF37]' : 'bg-[#555]'}`}
                        >
                          <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${security[opt.key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="aurem-glass-card rounded-xl p-6">
                  <h2 className="text-sm font-medium mb-4" style={{ color: 'var(--aurem-heading)' }}>Active Sessions</h2>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded-lg border border-[#4ade80]/20" style={{ background: 'var(--aurem-surface)' }}>
                      <div className="flex items-center gap-3">
                        <Globe className="w-4 h-4 text-[#4ade80]" />
                        <div>
                          <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>Current Session</p>
                          <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Chrome - Active now</p>
                        </div>
                      </div>
                      <span className="text-[10px] text-[#4ade80]">Current</span>
                    </div>
                  </div>
                  <button data-testid="logout-all-sessions-btn"
                    className="mt-4 flex items-center gap-2 px-4 py-2 text-[11px] text-[#ef4444] bg-[#ef4444]/10 border border-[#ef4444]/20 rounded-lg hover:bg-[#ef4444]/20 transition-colors">
                    <LogOut className="w-3.5 h-3.5" /> Sign Out All Other Sessions
                  </button>
                </div>
              </div>
            )}


            {/* API Keys Tab */}
            {activeTab === 'api-keys' && (
              <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-api-keys-tab">
                <ApiKeysSettingsInline token={token} />
              </div>
            )}

            {/* Notifications Tab */}
            {activeTab === 'notifications' && (
              <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-notifications">
                <h2 className="text-sm font-medium mb-6" style={{ color: 'var(--aurem-heading)' }}>Notification Preferences</h2>
                <div className="space-y-1">
                  {[
                    { key: 'email_alerts', label: 'Email Alerts', desc: 'Important system and account notifications' },
                    { key: 'push_notifications', label: 'Push Notifications', desc: 'Browser notifications for real-time events' },
                    { key: 'weekly_digest', label: 'Weekly Digest', desc: 'Summary of your platform activity every Monday' },
                    { key: 'security_alerts', label: 'Security Alerts', desc: 'Login attempts, password changes, new devices' },
                    { key: 'deal_updates', label: 'Deal Updates', desc: 'Notifications when deals progress or close' },
                    { key: 'agent_reports', label: 'Agent Reports', desc: 'Daily summaries from your AI agent swarm' },
                    { key: 'marketing', label: 'Product Updates', desc: 'New features, tips, and AUREM news' },
                  ].map(opt => (
                    <div key={opt.key} className="flex items-center justify-between p-4 rounded-lg transition-colors" style={{ ':hover': { background: 'var(--aurem-hover)' } }}>
                      <div>
                        <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{opt.label}</p>
                        <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{opt.desc}</p>
                      </div>
                      <button
                        onClick={() => setNotifications({ ...notifications, [opt.key]: !notifications[opt.key] })}
                        data-testid={`toggle-${opt.key}`}
                        className={`w-10 h-5 rounded-full transition-colors relative ${notifications[opt.key] ? 'bg-[#D4AF37]' : 'bg-[#555]'}`}
                      >
                        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${notifications[opt.key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="mt-6 pt-5 flex items-center justify-end gap-3" style={{ borderTop: '1px solid var(--aurem-divider)' }}>
                  {saved && (
                    <span className="flex items-center gap-1.5 text-[11px] text-[#4ade80]">
                      <Check className="w-3.5 h-3.5" /> Saved
                    </span>
                  )}
                  <button onClick={handleSaveNotifications} disabled={saving}
                    data-testid="save-notifications-btn"
                    className="flex items-center gap-2 px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">
                    <Save className="w-3.5 h-3.5" />
                    {saving ? 'Saving...' : 'Save Preferences'}
                  </button>
                </div>
              </div>
            )}

            {/* Integrations Tab */}
            {activeTab === 'integrations' && (
              <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-integrations">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>Service Connections</h2>
                  <button onClick={fetchIntegrations} style={{ color: 'var(--aurem-body-secondary)' }} data-testid="refresh-integrations-btn">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="space-y-2">
                  {integrations.length > 0 ? integrations.map((svc, idx) => {
                    const modeConfig = {
                      live:           { label: 'Live',           dotColor: '#4ade80', textColor: '#4ade80' },
                      mock:           { label: 'Mock',           dotColor: '#f59e0b', textColor: '#f59e0b' },
                      not_configured: { label: 'Not Configured', dotColor: '#888',    textColor: '#888' },
                      unavailable:    { label: 'Unavailable',    dotColor: '#ef4444', textColor: '#ef4444' },
                    }[svc.mode] || { label: svc.mode, dotColor: '#888', textColor: '#888' };
                    const Icon = svc.icon;
                    return (
                      <div key={idx} className="flex items-center justify-between p-4 rounded-lg transition-colors" style={{ background: 'var(--aurem-surface)' }} data-testid={`integration-${idx}`}>
                        <div className="flex items-center gap-3">
                          <Icon className="w-5 h-5" style={{ color: modeConfig.textColor }} />
                          <div>
                            <p className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>{svc.name}</p>
                            <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{svc.message || `${svc.category} integration`}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium" style={{ color: modeConfig.textColor, background: `${modeConfig.dotColor}15` }}>
                          <div className="w-1.5 h-1.5 rounded-full" style={{ background: modeConfig.dotColor }} />
                          {modeConfig.label}
                        </div>
                      </div>
                    );
                  }) : (
                    <div className="text-center py-8">
                      <Plug className="w-6 h-6 mx-auto mb-2" style={{ color: 'var(--aurem-body-secondary)' }} />
                      <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Loading integration status...</p>
                    </div>
                  )}
                </div>
                <div className="mt-5 p-4 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Zap className="w-4 h-4 text-[#D4AF37] mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>Transition to Live</p>
                      <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>Services in <span className="text-[#f59e0b] font-medium">Mock</span> mode use simulated data. Add your API keys via the Secret Vault to activate live connections.</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Infrastructure Tab — Redis, CORS, Indexes */}
            {activeTab === 'infrastructure' && <InfrastructureTab token={token} inputCls={inputCls} />}

            {/* LinkedIn Tab — iter 282aj: OAuth connect + publish stats */}
            {activeTab === 'linkedin' && <LinkedInTab token={token} />}

            {/* Team Tab */}
            {activeTab === 'team' && (
              <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-team">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>Team Members</h2>
                  <button data-testid="invite-member-btn"
                    className="flex items-center gap-2 px-4 py-2 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity">
                    <Users className="w-3.5 h-3.5" /> Invite Member
                  </button>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 rounded-lg" style={{ background: 'var(--aurem-surface)' }}>
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-[#D4AF37]/10 flex items-center justify-center text-sm font-semibold text-[#D4AF37]">
                        {(user?.first_name || 'A')[0]}
                      </div>
                      <div>
                        <p className="text-xs" style={{ color: 'var(--aurem-heading)' }}>{user?.first_name} {user?.last_name}</p>
                        <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{user?.email}</p>
                      </div>
                    </div>
                    <span className="px-2.5 py-1 text-[10px] font-medium bg-[#D4AF37]/10 text-[#D4AF37] rounded-full">Owner</span>
                  </div>
                </div>
                <div className="mt-8 p-5 bg-[#D4AF37]/5 border border-[#D4AF37]/10 rounded-lg text-center">
                  <Users className="w-6 h-6 text-[#D4AF37] mx-auto mb-2" />
                  <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Invite team members to collaborate on your AUREM workspace</p>
                  <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>Each member can be assigned specific roles and permissions</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


/* ═══════════════════════════════════════════════════════════ */
/* INFRASTRUCTURE TAB — Redis, CORS, MongoDB Indexes          */
/* ═══════════════════════════════════════════════════════════ */
function InfrastructureTab({ token, inputCls }) {
  const [config, setConfig] = useState(null);
  const [redisUrl, setRedisUrl] = useState('');
  const [testingRedis, setTestingRedis] = useState(false);
  const [redisResult, setRedisResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [creatingIndexes, setCreatingIndexes] = useState(false);
  const [indexResult, setIndexResult] = useState(null);

  const headers = useMemo(() => ({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }), [token]);
  const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/infrastructure`, { headers });
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        setRedisUrl(data.redis_url || '');
      }
    } catch (e) { console.error(e); }
  }, [headers]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const saveRedisUrl = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/api/settings/infrastructure`, {
        method: 'PUT', headers,
        body: JSON.stringify({ redis_url: redisUrl }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        fetchConfig();
      }
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const testRedis = async () => {
    setTestingRedis(true); setRedisResult(null);
    try {
      const res = await fetch(`${API}/api/settings/infrastructure/test-redis`, {
        method: 'POST', headers,
        body: JSON.stringify({ redis_url: redisUrl }),
      });
      if (res.ok) setRedisResult(await res.json());
    } catch (e) { setRedisResult({ connected: false, error: e.message }); }
    finally { setTestingRedis(false); }
  };

  const createIndexes = async () => {
    setCreatingIndexes(true); setIndexResult(null);
    try {
      const res = await fetch(`${API}/api/settings/infrastructure/create-indexes`, {
        method: 'POST', headers,
      });
      if (res.ok) setIndexResult(await res.json());
    } catch (e) { setIndexResult({ success: false, error: e.message }); }
    finally { setCreatingIndexes(false); }
  };

  const missingIndexCount = config?.mongodb_indexes
    ? Object.values(config.mongodb_indexes).reduce((sum, c) => sum + (c.missing?.length || 0), 0)
    : 0;

  return (
    <div className="space-y-4" data-testid="settings-infrastructure">
      {/* Redis Configuration */}
      <div className="aurem-glass-card rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-[#FF6B00]" />
            <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>Redis Cache Layer</h2>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium" style={{
            color: config?.redis_connected ? '#4ade80' : '#f59e0b',
            background: config?.redis_connected ? 'rgba(74,222,128,0.1)' : 'rgba(245,158,11,0.1)',
          }}>
            <div className={`w-1.5 h-1.5 rounded-full ${config?.redis_connected ? 'bg-emerald-400' : 'bg-amber-400'}`} />
            {config?.redis_connected ? 'Connected' : 'In-Memory Fallback'}
          </div>
        </div>

        <div className="p-3 rounded-lg mb-4" style={{ background: 'rgba(255,107,0,0.06)', border: '1px solid rgba(255,107,0,0.12)' }}>
          <p className="text-[11px]" style={{ color: 'var(--aurem-body-secondary)' }}>
            <strong style={{ color: '#FF6B00' }}>Why Redis?</strong> Moves session state and rate limiting off MongoDB. Reduces V2V voice latency and enables cross-instance caching.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-[10px] mb-1.5 tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>REDIS URL</label>
            <input
              type="text" value={redisUrl} onChange={(e) => setRedisUrl(e.target.value)}
              placeholder="redis://default:your-password@your-host.upstash.io:6379"
              data-testid="redis-url-input"
              className={inputCls}
              style={{ background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}
            />
            <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)' }}>
              Free tier: <a href="https://console.upstash.com" target="_blank" rel="noopener noreferrer" className="text-[#FF6B00] underline">Upstash Console</a> — Create Database — Copy REST URL
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button onClick={saveRedisUrl} disabled={saving} data-testid="save-redis-btn"
              className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">
              <Save className="w-3.5 h-3.5" /> {saving ? 'Saving...' : 'Save Redis URL'}
            </button>
            <button onClick={testRedis} disabled={testingRedis} data-testid="test-redis-btn"
              className="flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg transition-colors"
              style={{ border: '1px solid var(--aurem-input-border)', color: 'var(--aurem-heading)' }}>
              <Activity className="w-3.5 h-3.5" /> {testingRedis ? 'Testing...' : 'Test Connection'}
            </button>
            {saved && <span className="text-[11px] text-[#4ade80] flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Saved</span>}
          </div>

          {redisResult && (
            <div className="p-3 rounded-lg" style={{
              background: redisResult.connected ? 'rgba(74,222,128,0.06)' : 'rgba(239,68,68,0.06)',
              border: `1px solid ${redisResult.connected ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)'}`,
            }} data-testid="redis-test-result">
              {redisResult.connected ? (
                <div className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-emerald-500" />
                  <span className="text-xs text-emerald-500 font-medium">Connected</span>
                  <span className="text-[10px] ml-auto" style={{ color: 'var(--aurem-body-secondary)' }}>
                    Memory: {redisResult.used_memory} | Latency: {redisResult.latency_ms}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs text-red-400 font-medium">Failed</span>
                  <span className="text-[10px] ml-2" style={{ color: 'var(--aurem-body-secondary)' }}>{redisResult.error}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* MongoDB Indexes */}
      <div className="aurem-glass-card rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#D4AF37]" />
            <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>MongoDB Performance Indexes</h2>
          </div>
          {missingIndexCount > 0 && (
            <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-400/10 text-amber-400 rounded-full border border-amber-400/20">
              {missingIndexCount} missing
            </span>
          )}
        </div>

        <div className="p-3 rounded-lg mb-4" style={{ background: 'rgba(212,175,55,0.06)', border: '1px solid rgba(212,175,55,0.12)' }}>
          <p className="text-[11px]" style={{ color: 'var(--aurem-body-secondary)' }}>
            <strong style={{ color: '#D4AF37' }}>Performance boost:</strong> Indexes on hot collections (leads, audit_chain, voice_calls, pipeline_runs) reduce query time from O(n) to O(log n).
          </p>
        </div>

        {config?.mongodb_indexes && (
          <div className="space-y-1.5 mb-4 max-h-48 overflow-y-auto">
            {Object.entries(config.mongodb_indexes).map(([name, info]) => (
              <div key={name} className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--aurem-input-bg)' }}>
                <span className="text-xs font-mono" style={{ color: 'var(--aurem-heading)' }}>{name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>{info.total_indexes || 0} indexes</span>
                  {info.missing?.length > 0 ? (
                    <span className="text-[10px] text-amber-400">{info.missing.length} missing</span>
                  ) : (
                    <Check className="w-3 h-3 text-emerald-400" />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <button onClick={createIndexes} disabled={creatingIndexes} data-testid="create-indexes-btn"
          className="flex items-center gap-2 px-5 py-2 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50">
          <Database className="w-3.5 h-3.5" /> {creatingIndexes ? 'Creating...' : 'Create All Indexes'}
        </button>

        {indexResult && (
          <div className="mt-3 p-3 rounded-lg" style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)' }}>
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-500" />
              <span className="text-xs text-emerald-500 font-medium">
                Indexes created on {indexResult.indexes_created?.length || 0} collections
              </span>
            </div>
          </div>
        )}
      </div>

      {/* CORS Info (read-only display) */}
      <div className="aurem-glass-card rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-[#4ade80]" />
          <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>CORS & Security</h2>
        </div>
        <div className="space-y-2">
          <p className="text-[10px] tracking-wider" style={{ color: 'var(--aurem-body-secondary)' }}>ALLOWED ORIGINS</p>
          <div className="flex flex-wrap gap-1.5">
            {(config?.cors_origins || []).map((origin, i) => (
              <span key={i} className="px-2.5 py-1 rounded text-[10px] font-mono" style={{
                background: 'var(--aurem-input-bg)', border: '1px solid var(--aurem-input-border)', color: '#4ade80',
              }}>{origin}</span>
            ))}
          </div>
          <p className="text-[10px] mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>
            CORS origins are set server-side for security. Contact admin to modify.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── iter 282aj — LinkedIn Publisher Settings Tab ─── */
function LinkedInTab({ token }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ last_post: null, posts_month: 0 });
  const [disconnecting, setDisconnecting] = useState(false);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/linkedin/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (r.ok) setStatus(await r.json());
    } catch {}
    // Stats (posts this month, last post) — best effort via admin feed, falls back to 0
    try {
      const r = await fetch(`${API_URL}/api/linkedin/stats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (r.ok) setStats(await r.json());
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  const handleConnect = () => {
    window.location.href = `${API_URL}/api/linkedin/auth`;
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await fetch(`${API_URL}/api/linkedin/disconnect`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      await fetchStatus();
    } catch {}
    setDisconnecting(false);
  };

  const connected = status?.connected;
  return (
    <div className="aurem-glass-card rounded-xl p-6" data-testid="settings-linkedin">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Linkedin className="w-4 h-4" style={{ color: '#0A66C2' }} />
          <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>LinkedIn Publisher</h2>
        </div>
        <button onClick={fetchStatus} style={{ color: 'var(--aurem-body-secondary)' }} data-testid="linkedin-refresh-btn">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Status row */}
      <div className="flex items-center justify-between p-4 rounded-lg mb-4" style={{ background: 'var(--aurem-surface)' }} data-testid="linkedin-status-row">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full" style={{ background: connected ? '#4ade80' : '#ef4444' }} data-testid="linkedin-status-dot" />
          <div>
            <p className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>
              {connected ? 'Connected' : 'Not Connected'}
            </p>
            {connected && status?.profile_name && (
              <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>{status.profile_name}</p>
            )}
            {connected && status?.expires_at && (
              <p className="text-[10px] mt-0.5" style={{ color: 'var(--aurem-body-secondary)' }}>
                Expires {new Date(status.expires_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
        {connected ? (
          <button onClick={handleDisconnect} disabled={disconnecting}
            className="px-3 py-1.5 text-[11px] font-medium rounded-lg border transition-colors"
            style={{ borderColor: 'rgba(239,68,68,0.3)', color: '#ef4444' }}
            data-testid="linkedin-disconnect-btn">
            {disconnecting ? 'Disconnecting…' : 'Disconnect'}
          </button>
        ) : (
          <button onClick={handleConnect}
            className="px-4 py-2 text-[11px] font-semibold rounded-lg text-white transition-opacity hover:opacity-90"
            style={{ background: '#0A66C2' }}
            data-testid="linkedin-connect-btn">
            Connect LinkedIn
          </button>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-4 rounded-lg" style={{ background: 'var(--aurem-surface)' }} data-testid="linkedin-posts-month">
          <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Posts this month</p>
          <p className="text-xl mt-1 font-semibold" style={{ color: '#D4AF37' }}>{stats?.posts_month ?? 0}</p>
        </div>
        <div className="p-4 rounded-lg" style={{ background: 'var(--aurem-surface)' }} data-testid="linkedin-last-post">
          <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Last published</p>
          <p className="text-xs mt-1" style={{ color: 'var(--aurem-heading)' }}>
            {stats?.last_post ? `${stats.last_post.post_type} · ${new Date(stats.last_post.ts).toLocaleDateString()}` : '—'}
          </p>
        </div>
      </div>

      <div className="mt-5 p-4 bg-[#0A66C2]/5 border border-[#0A66C2]/10 rounded-lg">
        <p className="text-xs font-medium" style={{ color: 'var(--aurem-heading)' }}>Auto-published types</p>
        <ul className="mt-2 space-y-1 text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>
          <li>• <b>case_study</b> — fires on every new client onboard</li>
          <li>• <b>weekly_tip</b> — every Monday 9 AM UTC</li>
          <li>• <b>repair_win</b> — fires on any website repair delivered</li>
        </ul>
      </div>
    </div>
  );
}


/* ─── Business ID Settings Tab ─── */
function BusinessIdTab({ token }) {
  const [bizData, setBizData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [qrData, setQrData] = useState(null);
  const [team, setTeam] = useState([]);
  const [teamCount, setTeamCount] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [confirmRegen, setConfirmRegen] = useState(false);

  useEffect(() => {
    if (!token) return;
    const h = { 'Authorization': `Bearer ${token}` };
    fetch(`${API_URL}/api/business-id/mine`, { headers: h })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setBizData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
    fetch(`${API_URL}/api/business-id/team`, { headers: h })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) { setTeam(d.connections || []); setTeamCount(d.count || 0); } })
      .catch(() => {});
  }, [headers]);

  const copyBid = () => {
    if (bizData?.business_id) {
      navigator.clipboard?.writeText(bizData.business_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const loadQR = async () => {
    if (!bizData?.business_id) return;
    try {
      const res = await fetch(`${API_URL}/api/business-id/qr/${bizData.business_id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const d = await res.json();
        setQrData(d);
        setShowQR(true);
      }
    } catch {}
  };

  const handleRegenerate = async () => {
    if (!confirmRegen) { setConfirmRegen(true); return; }
    setRegenerating(true);
    try {
      const res = await fetch(`${API_URL}/api/business-id/regenerate`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const d = await res.json();
        setBizData(prev => ({ ...prev, business_id: d.business_id }));
        setTeam([]);
        setTeamCount(0);
        setConfirmRegen(false);
      }
    } catch {}
    setRegenerating(false);
  };

  if (loading) return <div className="p-6 text-center" style={{ color: 'var(--aurem-body-secondary)' }}>Loading...</div>;

  const bid = bizData?.business_id || '---';

  return (
    <div className="space-y-6" data-testid="settings-business-id">
      <div className="aurem-glass-card rounded-xl p-6">
        <h2 className="text-sm font-medium mb-6" style={{ color: 'var(--aurem-heading)' }}>Your Business ID</h2>
        <div className="flex items-center gap-4 mb-6">
          <div data-testid="business-id-display" className="px-6 py-3 rounded-lg" style={{ background: 'rgba(255,107,0,0.06)', border: '1px solid rgba(255,107,0,0.2)', fontFamily: "'JetBrains Mono',monospace", fontSize: 18, fontWeight: 700, color: '#FF6B00', letterSpacing: '0.08em' }}>
            {bid}
          </div>
          <button data-testid="copy-business-id" onClick={copyBid} className="flex items-center gap-2 px-4 py-2 rounded-lg transition-colors" style={{ background: 'rgba(255,107,0,0.08)', border: '1px solid rgba(255,107,0,0.15)', color: '#FF6B00', cursor: 'pointer', fontSize: 12 }}>
            {copied ? <><Check size={14} /> Copied</> : <><Copy size={14} /> Copy</>}
          </button>
        </div>

        <div className="flex flex-wrap gap-3 mb-6">
          <button data-testid="show-qr-code" onClick={loadQR} className="flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-body)', cursor: 'pointer', fontSize: 12 }}>
            <QrCode size={14} /> Show QR Code
          </button>
          <button data-testid="regenerate-bid" onClick={handleRegenerate} className="flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all" style={{ background: confirmRegen ? 'rgba(239,68,68,0.12)' : 'rgba(255,255,255,0.03)', border: `1px solid ${confirmRegen ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.08)'}`, color: confirmRegen ? '#EF4444' : 'var(--aurem-body)', cursor: 'pointer', fontSize: 12 }}>
            <RefreshCw size={14} className={regenerating ? 'animate-spin' : ''} />
            {confirmRegen ? 'Confirm Regenerate?' : 'Regenerate ID'}
          </button>
        </div>

        {confirmRegen && (
          <div className="p-3 rounded-lg mb-4" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)' }}>
            <p className="text-xs" style={{ color: '#EF4444' }}>This will disconnect all devices using the current ID. This action cannot be undone.</p>
          </div>
        )}

        {showQR && qrData && (
          <div data-testid="qr-code-display" className="p-4 rounded-lg mb-6 text-center" style={{ background: 'rgba(255,107,0,0.04)', border: '1px solid rgba(255,107,0,0.1)' }}>
            <img src={`data:image/png;base64,${qrData.qr_base64}`} alt="Business QR" style={{ width: 180, height: 180, margin: '0 auto 12px', borderRadius: 8 }} />
            <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>Scan to connect a new device</p>
            <p className="text-[10px] mt-1" style={{ color: 'var(--aurem-body-secondary)', fontFamily: "'JetBrains Mono',monospace" }}>{qrData.url_encoded}</p>
          </div>
        )}

        <div className="p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
          <p className="text-xs font-medium mb-2" style={{ color: 'var(--aurem-heading)' }}>Share with team:</p>
          <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)', lineHeight: 1.6 }}>
            "Open <span style={{ color: '#FF6B00' }}>aurem.live/ora</span> and enter code <span style={{ fontFamily: "'JetBrains Mono',monospace", color: '#FF6B00', fontWeight: 600 }}>{bid}</span>"
          </p>
        </div>
      </div>

      <div className="aurem-glass-card rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-medium" style={{ color: 'var(--aurem-heading)' }}>Connected Devices</h2>
          <span className="text-xs px-2 py-1 rounded-full" style={{ background: 'rgba(255,107,0,0.08)', color: '#FF6B00' }}>{teamCount}</span>
        </div>
        {team.length === 0 ? (
          <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>No team members connected yet. Share your Business ID to get started.</p>
        ) : (
          <div className="space-y-2">
            {team.map((c, i) => (
              <div key={i} data-testid={`team-device-${i}`} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                <div>
                  <p className="text-xs" style={{ color: 'var(--aurem-body)' }}>{c.user_agent || 'Unknown device'}</p>
                  <p className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Connected: {c.connected_at ? new Date(c.connected_at).toLocaleDateString() : '---'}</p>
                </div>
                <span className="text-[10px]" style={{ color: 'var(--aurem-body-secondary)' }}>Last active: {c.last_active ? new Date(c.last_active).toLocaleDateString() : '---'}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Resend Welcome */}
      <div className="aurem-glass-card rounded-xl p-6">
        <h2 className="text-sm font-medium mb-4" style={{ color: 'var(--aurem-heading)' }}>Welcome Package</h2>
        <button
          data-testid="settings-resend-welcome"
          onClick={async () => {
            try {
              await fetch(`${API_URL}/api/business-id/resend-welcome`, {
                method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
              });
              alert('Welcome email resent!');
            } catch {}
          }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--aurem-body)', cursor: 'pointer', fontSize: 12 }}
        >
          <Mail size={14} /> Resend Welcome Email
        </button>
        <p className="text-[10px] mt-2" style={{ color: 'var(--aurem-body-secondary)' }}>Resend your Business ID, QR code, and setup instructions to your email.</p>
      </div>

      {/* Danger Zone */}
      <div className="aurem-glass-card rounded-xl p-6" style={{ border: '1px solid rgba(239,68,68,0.15)' }}>
        <h2 className="text-sm font-medium mb-4" style={{ color: '#EF4444' }}>Danger Zone</h2>
        <button data-testid="regenerate-bid-danger" onClick={handleRegenerate} className="flex items-center gap-2 px-4 py-2.5 rounded-lg transition-all" style={{ background: confirmRegen ? 'rgba(239,68,68,0.12)' : 'rgba(239,68,68,0.04)', border: `1px solid ${confirmRegen ? 'rgba(239,68,68,0.3)' : 'rgba(239,68,68,0.12)'}`, color: confirmRegen ? '#EF4444' : '#E8816A', cursor: 'pointer', fontSize: 12 }}>
          <RefreshCw size={14} className={regenerating ? 'animate-spin' : ''} />
          {confirmRegen ? 'Confirm: Regenerate ID?' : 'Regenerate Business ID'}
        </button>
        {confirmRegen && (
          <p className="text-xs mt-2" style={{ color: '#EF4444' }}>Warning: This will disconnect all devices using {bid}.</p>
        )}
      </div>
    </div>
  );
}
