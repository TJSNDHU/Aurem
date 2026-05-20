/**
 * AUREM Client Manager
 * Admin panel to onboard and manage multiple business clients.
 * All credentials stored encrypted. One window to manage everything.
 */
import React, { useState, useEffect, useCallback } from 'react';
import useLivePolling from '../hooks/useLivePolling';
import {
  Users, Plus, Search, ChevronDown, ChevronRight, Check, X,
  Mail, MessageCircle, Phone, Globe, Instagram, Youtube,
  Linkedin, Twitter, Facebook, Smartphone, Settings, Shield,
  Play, Pause, Trash2, RefreshCw, Zap, Eye, EyeOff,
  Building2, User, Star, Copy, ExternalLink, BarChart3,
  CheckCircle, AlertCircle, Clock, FileText, Download, Loader2,
  Package
} from 'lucide-react';
import CustomerServicesPopup from './CustomerServicesPopup';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;

const CARRIERS = [
  { value: 'tmobile', label: 'T-Mobile' }, { value: 'att', label: 'AT&T' },
  { value: 'verizon', label: 'Verizon' }, { value: 'sprint', label: 'Sprint' },
  { value: 'rogers', label: 'Rogers' }, { value: 'bell', label: 'Bell' },
  { value: 'telus', label: 'Telus' }, { value: 'fido', label: 'Fido' },
  { value: 'ee', label: 'EE' }, { value: 'vodafone', label: 'Vodafone' },
  { value: 'o2', label: 'O2' }, { value: 'jio', label: 'Jio' },
  { value: 'airtel', label: 'Airtel' },
];

const INDUSTRIES = [
  'Skincare & Aesthetics', 'Healthcare', 'Beauty & Wellness', 'Fitness',
  'Restaurant & Food', 'Retail & E-commerce', 'Real Estate', 'Legal',
  'Consulting', 'Education', 'Technology', 'Other'
];

const STATUS_CONFIG = {
  active: { color: '#4ade80', label: 'Active', icon: CheckCircle },
  paused: { color: '#f59e0b', label: 'Paused', icon: Pause },
  setup: { color: '#3b82f6', label: 'Setup', icon: Settings },
};

function ClientForm({ client, onSave, onCancel, saving }) {
  const [form, setForm] = useState({
    business_name: '', industry: '', website: '', contact_person: '',
    contact_email: '', contact_phone: '', logo_url: '',
    gmail_email: '', gmail_app_password: '', gmail_keywords: '',
    whatsapp_number: '', meta_access_token: '', meta_phone_id: '',
    instagram_handle: '', facebook_page_id: '', youtube_channel: '',
    linkedin_url: '', twitter_handle: '',
    sms_phone: '', sms_carrier: '',
    brand_tagline: '', default_discount: '10', welcome_message: '',
    whatsapp_prefill: '', automation_mode: 'auto',
    ...(client || {})
  });
  const [activeSection, setActiveSection] = useState('business');
  const [showPasswords, setShowPasswords] = useState({});

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const togglePw = (k) => setShowPasswords(p => ({ ...p, [k]: !p[k] }));

  const sections = [
    { id: 'business', label: 'Business Info', icon: Building2, color: '#D4AF37' },
    { id: 'gmail', label: 'Gmail & Email', icon: Mail, color: '#EA4335' },
    { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle, color: '#25D366' },
    { id: 'social', label: 'Social Media', icon: Globe, color: '#3b82f6' },
    { id: 'sms', label: 'SMS', icon: Smartphone, color: '#f59e0b' },
    { id: 'campaign', label: 'Campaign', icon: Zap, color: '#a855f7' },
  ];

  const Field = ({ label, field, type = 'text', placeholder, sensitive, mono }) => (
    <div>
      <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider">{label}</label>
      <div className="relative">
        <input
          type={sensitive && !showPasswords[field] ? 'password' : type}
          value={form[field] || ''}
          onChange={e => set(field, e.target.value)}
          placeholder={placeholder}
          data-testid={`client-${field}`}
          className={`w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50 ${mono ? 'font-mono' : ''}`}
        />
        {sensitive && (
          <button type="button" onClick={() => togglePw(field)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#555] hover:text-[#888]">
            {showPasswords[field] ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[10000]">
      <div className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-2xl w-full max-w-3xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-[#FF6B00]/20">
          <h3 className="text-sm font-medium text-[#1A1A2E]">{client ? 'Edit Client' : 'Add New Client'}</h3>
          <button onClick={onCancel} className="text-[#555] hover:text-[#555]"><X className="size-5" /></button>
        </div>

        {/* Section Tabs */}
        <div className="flex gap-1 px-5 pt-4 pb-2 overflow-x-auto">
          {sections.map(s => (
            <button key={s.id} onClick={() => setActiveSection(s.id)} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[10px] whitespace-nowrap transition-all ${activeSection === s.id ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30' : 'text-[#666] hover:text-[#555]'}`}>
              <s.icon className="size-3" style={{ color: s.color }} />{s.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-5">
          {activeSection === 'business' && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="BUSINESS NAME *" field="business_name" placeholder="AUREM Aesthetics" />
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider">INDUSTRY</label>
                  <select value={form.industry} onChange={e => set('industry', e.target.value)} data-testid="client-industry" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] outline-none focus:border-[#D4AF37]/50">
                    <option value="">Select industry…</option>
                    {INDUSTRIES.map(i => <option key={i} value={i}>{i}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="CONTACT PERSON" field="contact_person" placeholder="John Smith" />
                <Field label="CONTACT EMAIL" field="contact_email" placeholder="contact@company.com" type="email" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="CONTACT PHONE" field="contact_phone" placeholder="+1 416 555 0123" />
                <Field label="WEBSITE" field="website" placeholder="https://reroots.com" />
              </div>
              <Field label="LOGO URL" field="logo_url" placeholder="https://..." />
            </div>
          )}

          {activeSection === 'gmail' && (
            <div className="space-y-3">
              <div className="p-3 bg-[#EA4335]/5 border border-[#EA4335]/10 rounded-lg">
                <p className="text-[10px] text-[#EA4335] font-medium">Gmail credentials are encrypted with AES-256</p>
                <p className="text-[9px] text-[#888]">App Password: Google Account → Security → 2-Step Verification → App passwords</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="GMAIL ADDRESS" field="gmail_email" placeholder="business@gmail.com" type="email" />
                <Field label="GMAIL APP PASSWORD" field="gmail_app_password" placeholder="xxxx xxxx xxxx xxxx" sensitive mono />
              </div>
              <Field label="MONITOR KEYWORDS" field="gmail_keywords" placeholder="New Inquiry, Consultation, Booking" />
              {client?.has_gmail_password && !form.gmail_app_password && (
                <div className="flex items-center gap-2 text-[10px] text-[#4ade80]"><Shield className="size-3" /> Password already stored (encrypted). Leave blank to keep current.</div>
              )}
            </div>
          )}

          {activeSection === 'whatsapp' && (
            <div className="space-y-3">
              <div className="p-3 bg-[#25D366]/5 border border-[#25D366]/10 rounded-lg">
                <p className="text-[10px] text-[#25D366] font-medium">1,000 free conversations/month via Meta Cloud API</p>
                <p className="text-[9px] text-[#888]">Register at <a href="https://developers.facebook.com" target="_blank" rel="noopener noreferrer" className="text-[#25D366] underline">developers.facebook.com</a></p>
              </div>
              <Field label="WHATSAPP NUMBER" field="whatsapp_number" placeholder="15551234567" mono />
              <div className="grid grid-cols-2 gap-3">
                <Field label="META ACCESS TOKEN" field="meta_access_token" placeholder="Your Meta token" sensitive mono />
                <Field label="PHONE NUMBER ID" field="meta_phone_id" placeholder="Meta phone ID" mono />
              </div>
              <Field label="WHATSAPP PRE-FILL MESSAGE" field="whatsapp_prefill" placeholder="Hi! I'd like to know more about..." />
              {client?.has_meta_token && !form.meta_access_token && (
                <div className="flex items-center gap-2 text-[10px] text-[#4ade80]"><Shield className="size-3" /> Token already stored (encrypted). Leave blank to keep current.</div>
              )}
            </div>
          )}

          {activeSection === 'social' && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider flex items-center gap-1"><Instagram className="size-3 text-[#E4405F]" /> INSTAGRAM</label>
                  <input type="text" value={form.instagram_handle} onChange={e => set('instagram_handle', e.target.value)} placeholder="@your_business" data-testid="client-instagram" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
                </div>
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider flex items-center gap-1"><Facebook className="size-3 text-[#1877F2]" /> FACEBOOK PAGE ID</label>
                  <input type="text" value={form.facebook_page_id} onChange={e => set('facebook_page_id', e.target.value)} placeholder="Page ID or URL" data-testid="client-facebook" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider flex items-center gap-1"><Youtube className="size-3 text-[#FF0000]" /> YOUTUBE</label>
                  <input type="text" value={form.youtube_channel} onChange={e => set('youtube_channel', e.target.value)} placeholder="Channel URL" data-testid="client-youtube" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
                </div>
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider flex items-center gap-1"><Linkedin className="size-3 text-[#0A66C2]" /> LINKEDIN</label>
                  <input type="text" value={form.linkedin_url} onChange={e => set('linkedin_url', e.target.value)} placeholder="Profile/Company URL" data-testid="client-linkedin" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
                </div>
              </div>
              <div>
                <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider flex items-center gap-1"><Twitter className="size-3 text-[#999]" /> X (TWITTER)</label>
                <input type="text" value={form.twitter_handle} onChange={e => set('twitter_handle', e.target.value)} placeholder="@handle" data-testid="client-twitter" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
              </div>
            </div>
          )}

          {activeSection === 'sms' && (
            <div className="space-y-3">
              <div className="p-3 bg-[#f59e0b]/5 border border-[#f59e0b]/10 rounded-lg">
                <p className="text-[10px] text-[#f59e0b] font-medium">Free SMS via email-to-carrier gateway</p>
                <p className="text-[9px] text-[#888]">~100 texts/day on free Gmail, ~2,000/day on Workspace</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="SMS PHONE NUMBER" field="sms_phone" placeholder="4161234567" mono />
                <div>
                  <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider">CARRIER</label>
                  <select value={form.sms_carrier} onChange={e => set('sms_carrier', e.target.value)} data-testid="client-sms-carrier" className="w-full px-3 py-2.5 bg-white/50 border border-[#FF6B00]/15 rounded-lg text-xs text-[#1A1A2E] outline-none focus:border-[#D4AF37]/50">
                    <option value="">Select carrier…</option>
                    {CARRIERS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'campaign' && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="BRAND TAGLINE" field="brand_tagline" placeholder="Scientific-Luxe Skincare" />
                <Field label="DEFAULT DISCOUNT %" field="default_discount" placeholder="10" />
              </div>
              <Field label="WELCOME MESSAGE" field="welcome_message" placeholder="Welcome to our exclusive consultation..." />
              <div>
                <label className="block text-[10px] text-[#5a5a72] mb-1 tracking-wider">AUTOMATION MODE</label>
                <div className="flex gap-2">
                  {[
                    { id: 'auto', label: 'Auto', desc: 'Fully automated', icon: Zap, color: '#4ade80' },
                    { id: 'manual', label: 'Manual Override', desc: 'Review before sending', icon: User, color: '#f59e0b' },
                  ].map(m => (
                    <button key={m.id} type="button" onClick={() => set('automation_mode', m.id)} className={`flex-1 p-3 rounded-lg border text-left transition-colors ${form.automation_mode === m.id ? 'bg-[#D4AF37]/5 border-[#D4AF37]/30' : 'bg-white/50 border-[#FF6B00]/15'}`}>
                      <div className="flex items-center gap-2 mb-1"><m.icon className="size-3.5" style={{ color: m.color }} /><span className="text-xs text-[#1A1A2E]">{m.label}</span></div>
                      <p className="text-[9px] text-[#555]">{m.desc}</p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="flex gap-3 p-5 border-t border-[#FF6B00]/20">
          <button onClick={onCancel} className="flex-1 px-4 py-2.5 text-xs text-[#888] border border-[#FF6B00]/15 rounded-lg hover:bg-white/50">Cancel</button>
          <button onClick={() => onSave(form)} disabled={!form.business_name || saving} data-testid="save-client-btn" className="flex-1 px-4 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90 disabled:opacity-50">
            {saving ? 'Saving...' : client ? 'Update Client' : 'Add Client'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ClientManager({ token, user, onViewCustomer }) {
  const [clients, setClients] = useState([]);
  const [stats, setStats] = useState({ total: 0, active: 0, paused: 0, setup: 0 });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editClient, setEditClient] = useState(null);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState(null);
  const [reportDropdown, setReportDropdown] = useState(null);
  const [generatingReport, setGeneratingReport] = useState(null);
  const [servicesPopupClient, setServicesPopupClient] = useState(null);
  // Platform Subscribers = people who signed up on aurem.live (db.platform_users).
  // Different from Managed Clients (db.managed_clients) which are the operator's B2B targets.
  const [subscribers, setSubscribers] = useState([]);
  const [showSubscribers, setShowSubscribers] = useState(false);
  // Password reset flow state
  const [resetTarget, setResetTarget] = useState(null);     // subscriber being reset
  const [resetInput, setResetInput] = useState('');         // custom password (empty => auto-generate)
  const [resetBusy, setResetBusy] = useState(false);
  const [resetResult, setResetResult] = useState(null);     // {email, new_password} shown once

  const h = { 'Authorization': `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    try {
      const [cR, sR, tcR] = await Promise.all([
        fetch(`${API_URL}/api/clients`, { headers: h }),
        fetch(`${API_URL}/api/clients/stats/overview`, { headers: h }),
        fetch(`${API_URL}/api/admin/customers`, { headers: h }),
      ]);
      let allClients = [];
      if (cR.ok) { const d = await cR.json(); allClients = d.clients || []; }
      // Merge tenant_customers as additional entries if not already in managed_clients
      if (tcR.ok) {
        const tc = await tcR.json();
        const existing = new Set(allClients.map(c => c.contact_email || c.business_name));
        for (const cust of (tc.customers || [])) {
          if (!existing.has(cust.email) && !existing.has(cust.company_name)) {
            allClients.push({
              id: cust.tenant_id,
              tenant_id: cust.tenant_id,
              business_name: cust.company_name,
              contact_person: cust.full_name,
              contact_email: cust.email,
              contact_phone: cust.phone,
              website: cust.website_url,
              industry: cust.industry,
              status: cust.is_active ? 'active' : 'paused',
              automation_mode: 'auto',
              plan: cust.plan,
              business_id: cust.business_id,
              _is_tenant_customer: true,
            });
          }
        }
      }
      setClients(allClients);
      if (sR.ok) { const d = await sR.json(); setStats(d); }
      else { setStats({ total: allClients.length, active: allClients.filter(c => c.status === 'active').length, paused: allClients.filter(c => c.status === 'paused').length, setup: allClients.filter(c => c.status === 'setup').length }); }

      // Platform Subscribers (admin-only) — who signed up on aurem.live
      try {
        const sRes = await fetch(`${API_URL}/api/clients/platform/subscribers`, { headers: h });
        if (sRes.ok) {
          const sd = await sRes.json();
          setSubscribers(sd.subscribers || []);
        }
      } catch { /* ignore — non-admin users just don't see this section */ }
    } catch { setClients([]); }    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);
  // iter 271 — live refresh every 15s (pauses in background)
  useLivePolling(fetchData, 15000);

  // Admin-only: force-reset a subscriber's password. Empty input auto-generates.
  const submitPasswordReset = async () => {
    if (!resetTarget) return;
    setResetBusy(true);
    try {
      const uid = resetTarget.id || resetTarget.user_id || resetTarget.email;
      const res = await fetch(
        `${API_URL}/api/clients/platform/subscribers/${encodeURIComponent(uid)}/reset-password`,
        {
          method: 'POST',
          headers: { ...h, 'Content-Type': 'application/json' },
          body: JSON.stringify(resetInput.trim() ? { new_password: resetInput.trim() } : {}),
        }
      );
      const data = await res.json();
      if (!res.ok) {
        alert(`Reset failed: ${data.detail || res.status}`);
      } else {
        setResetResult(data);
      }
    } catch (e) {
      alert(`Reset error: ${e.message}`);
    } finally {
      setResetBusy(false);
    }
  };

  const closeResetModal = () => {
    setResetTarget(null);
    setResetInput('');
    setResetResult(null);
  };

  const handleSave = async (form) => {
    setSaving(true);
    try {
      const url = editClient ? `${API_URL}/api/clients/${editClient.id}` : `${API_URL}/api/clients`;
      const method = editClient ? 'PUT' : 'POST';
      const res = await fetch(url, { method, headers: { ...h, 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
      if (res.ok) { setShowForm(false); setEditClient(null); fetchData(); }
    } catch (e) { console.error(e); }
    finally { setSaving(false); }
  };

  const handleToggle = async (id) => {
    try { await fetch(`${API_URL}/api/clients/${id}/toggle`, { method: 'PUT', headers: h }); fetchData(); } catch {}
  };

  const handleModeToggle = async (id, currentMode) => {
    const newMode = currentMode === 'auto' ? 'manual' : 'auto';
    try { await fetch(`${API_URL}/api/clients/${id}/mode`, { method: 'PUT', headers: { ...h, 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: newMode }) }); fetchData(); } catch {}
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this client? This cannot be undone.')) return;
    try { await fetch(`${API_URL}/api/clients/${id}`, { method: 'DELETE', headers: h }); fetchData(); } catch {}
  };

  const generateReport = async (client, format) => {
    setGeneratingReport(client.id);
    setReportDropdown(null);
    try {
      let endpoint, body;
      if (format === 'docx') {
        endpoint = `${API_URL}/api/docs/proposal`;
        body = { client_name: client.contact_person || client.business_name, business: client.business_name, services: [] };
      } else if (format === 'pptx') {
        endpoint = `${API_URL}/api/docs/health-deck`;
        body = { shop: client.business_name, metrics: {} };
      } else {
        endpoint = `${API_URL}/api/docs/campaign-report`;
        body = { campaign_name: `${client.business_name} Performance`, metrics: {} };
      }
      const res = await fetch(endpoint, { method: 'POST', headers: { ...h, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (res.ok) {
        const data = await res.json();
        if (data.doc_id) {
          const dlRes = await fetch(`${API_URL}/api/docs/download/${data.doc_id}`, { headers: h });
          if (dlRes.ok) {
            const blob = await dlRes.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${data.doc_id}.${format}`;
            a.click();
            URL.revokeObjectURL(url);
          }
        }
      }
    } catch (e) { console.error('Report generation failed:', e); }
    setGeneratingReport(null);
  };

  const filtered = clients.filter(c =>
    !search || c.business_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.contact_person?.toLowerCase().includes(search.toLowerCase()) ||
    c.industry?.toLowerCase().includes(search.toLowerCase())
  );

  const getChannelBadges = (c) => {
    const badges = [];
    if (c.gmail_email) badges.push({ icon: Mail, color: '#EA4335', label: 'Gmail' });
    if (c.whatsapp_number) badges.push({ icon: MessageCircle, color: '#25D366', label: 'WhatsApp' });
    if (c.instagram_handle) badges.push({ icon: Instagram, color: '#E4405F', label: 'IG' });
    if (c.facebook_page_id) badges.push({ icon: Facebook, color: '#1877F2', label: 'FB' });
    if (c.youtube_channel) badges.push({ icon: Youtube, color: '#FF0000', label: 'YT' });
    if (c.linkedin_url) badges.push({ icon: Linkedin, color: '#0A66C2', label: 'LI' });
    if (c.twitter_handle) badges.push({ icon: Twitter, color: '#999', label: 'X' });
    if (c.sms_phone) badges.push({ icon: Smartphone, color: '#f59e0b', label: 'SMS' });
    return badges;
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center bg-white/60" data-testid="client-manager-loading">
      <div className="flex items-center gap-3 text-[#666]"><RefreshCw className="size-5 animate-spin" /><span className="text-sm">Loading Client Manager…</span></div>
    </div>
  );

  return (
    <div className="flex-1 overflow-auto bg-white/60" data-testid="client-manager">
      <div className="max-w-6xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[#e2c97e] tracking-wider mb-1">Client Manager</h1>
            <p className="text-xs text-[#5a5a72]">Onboard businesses, store credentials, manage automation, all from one window</p>
          </div>
          <button onClick={() => { setEditClient(null); setShowForm(true); }} data-testid="add-client-btn" className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] text-xs font-semibold hover:opacity-90">
            <Plus className="size-3.5" /> Add Client
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Clients', value: stats.total, color: '#D4AF37', icon: Users },
            { label: 'Active', value: stats.active, color: '#4ade80', icon: CheckCircle },
            { label: 'Paused', value: stats.paused, color: '#f59e0b', icon: Pause },
            { label: 'Setup Needed', value: stats.setup, color: '#3b82f6', icon: Settings },
          ].map((s, i) => (
            <div key={i} className="p-4 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl">
              <s.icon className="size-5 mb-2" style={{ color: s.color }} />
              <div className="text-2xl font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
              <p className="text-[10px] text-[#555] mt-1">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Search */}
        <div className="flex gap-3 mb-4">
          <div className="flex-1 relative">
            <Search className="size-4 text-[#555] absolute left-3 top-1/2 -translate-y-1/2" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clients by name, contact, or industry..." data-testid="client-search" className="w-full pl-10 pr-4 py-2.5 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-lg text-xs text-[#1A1A2E] placeholder-[#555] outline-none focus:border-[#D4AF37]/50" />
          </div>
        </div>

        {/* Platform Subscribers (admin-only) — people who signed up on aurem.live */}
        {subscribers.length > 0 && (
          <div className="mb-5" data-testid="platform-subscribers-section">
            <div
              className="flex items-center justify-between p-3 bg-[#D4AF37]/5 border border-[#D4AF37]/30 rounded-lg cursor-pointer hover:bg-[#D4AF37]/10"
              onClick={() => setShowSubscribers(s => !s)}
              data-testid="platform-subscribers-toggle"
            >
              <div className="flex items-center gap-3">
                <div className="size-8 rounded-lg bg-[#D4AF37]/20 flex items-center justify-center text-[#D4AF37] font-bold">
                  {subscribers.length}
                </div>
                <div>
                  <div className="text-sm font-semibold text-[#e2c97e]">Platform Subscribers</div>
                  <div className="text-[10px] text-[#8B8170]">
                    People who signed up on aurem.live · stored in <code className="px-1 bg-black/30 rounded">db.platform_users</code>
                  </div>
                </div>
              </div>
              <span className="text-xs text-[#D4AF37]">{showSubscribers ? '▲ Hide' : '▼ Show'}</span>
            </div>
            {showSubscribers && (
              <div className="mt-2 space-y-2" data-testid="platform-subscribers-list">
                {subscribers.map((s, i) => (
                  <div
                    key={s.email || s.id || i}
                    data-testid={`subscriber-${i}`}
                    className="flex items-center justify-between p-3 bg-white/70 border border-[#FF6B00]/15 rounded-lg text-xs"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="size-8 rounded-full bg-[#8B7355]/20 flex items-center justify-center text-[#8B7355] font-bold text-xs">
                        {(s.full_name || s.email || '?')[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-[#1A1A2E] truncate">{s.full_name || '(no name)'}</div>
                        <div className="text-[#5C5C5C] truncate">{s.email}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
                      <span className="text-[#5C5C5C] hidden lg:inline truncate max-w-[160px]">{s.company_name || '—'}</span>
                      <span
                        className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase"
                        style={
                          s.role === 'admin' || s.role === 'super_admin'
                            ? { background: 'rgba(212,175,55,0.15)', color: '#D4AF37' }
                            : { background: 'rgba(139,115,85,0.15)', color: '#8B7355' }
                        }
                      >
                        {s.role || 'user'}
                      </span>
                      <span className="text-[#8B8170] text-[10px] hidden md:inline">
                        {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setResetTarget(s);
                          setResetInput('');
                          setResetResult(null);
                        }}
                        className="px-2 py-1 rounded text-[10px] font-semibold bg-[#ef4444]/10 text-[#ef4444] border border-[#ef4444]/30 hover:bg-[#ef4444]/20 transition flex-shrink-0"
                        data-testid={`reset-password-btn-${i}`}
                        title="Reset this subscriber's password"
                      >
                        🔑 Reset
                      </button>
                    </div>
                  </div>
                ))}
                <div className="text-[10px] text-[#8B8170] mt-2 px-1">
                  ⓘ These are your AUREM subscribers (tenants). Their B2B targets live below in Client Manager (<code className="px-1 bg-black/30 rounded">db.managed_clients</code>), scoped per subscriber.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Client List */}
        {filtered.length > 0 ? (
          <div className="space-y-3">
            {filtered.map(client => {
              const sc = STATUS_CONFIG[client.status] || STATUS_CONFIG.setup;
              const badges = getChannelBadges(client);
              const isExpanded = expandedId === client.id;

              return (
                <div key={client.id} data-testid={`client-${client.id}`} className="bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl overflow-hidden">
                  {/* Client Header */}
                  <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-white/40" onClick={() => setExpandedId(isExpanded ? null : client.id)}>
                    <div className="flex items-center gap-4">
                      <div className="size-11 rounded-xl bg-[#D4AF37]/10 flex items-center justify-center text-sm font-bold text-[#D4AF37]">
                        {client.business_name?.[0]?.toUpperCase() || 'C'}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-sm font-medium text-[#1A1A2E]">{client.business_name}</h3>
                          <span className="px-2 py-0.5 text-[9px] rounded-full flex items-center gap-1" style={{ backgroundColor: `${sc.color}12`, color: sc.color }}>
                            <sc.icon className="size-3" />{sc.label}
                          </span>
                          <span className={`px-2 py-0.5 text-[9px] rounded-full ${client.automation_mode === 'auto' ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-[#f59e0b]/10 text-[#f59e0b]'}`}>
                            {client.automation_mode === 'auto' ? 'Auto' : 'Manual'}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] text-[#555]">
                          {client.industry && <span>{client.industry}</span>}
                          {client.contact_person && <span>{client.contact_person}</span>}
                          <span>{client.leads_count || 0} leads</span>
                          {client.plan && <span className="px-1.5 py-0.5 rounded text-[9px] font-bold" style={{ background: client.plan === 'enterprise' ? 'rgba(168,85,247,0.1)' : client.plan === 'growth' ? 'rgba(59,130,246,0.1)' : 'rgba(212,175,55,0.1)', color: client.plan === 'enterprise' ? '#a855f7' : client.plan === 'growth' ? '#3b82f6' : '#D4AF37' }}>{client.plan}</span>}
                          {client.business_id && <span className="font-mono text-[9px] text-[#888]">{client.business_id}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {/* Channel Badges */}
                      <div className="flex gap-1">
                        {badges.map((b, i) => (
                          <div key={i} className="size-6 rounded flex items-center justify-center" style={{ backgroundColor: `${b.color}10` }} title={b.label}>
                            <b.icon className="size-3" style={{ color: b.color }} />
                          </div>
                        ))}
                      </div>
                      {/* Actions */}
                      <div className="flex items-center gap-1">
                        <button onClick={e => { e.stopPropagation(); handleModeToggle(client.id, client.automation_mode); }} title="Toggle auto/manual" className="p-1.5 rounded-md text-[#888] hover:text-[#1A1A2E] hover:bg-white/50">
                          {client.automation_mode === 'auto' ? <Zap className="size-3.5 text-[#4ade80]" /> : <User className="size-3.5 text-[#f59e0b]" />}
                        </button>
                        <button onClick={e => { e.stopPropagation(); handleToggle(client.id); }} title="Pause/Resume" className="p-1.5 rounded-md text-[#888] hover:text-[#1A1A2E] hover:bg-white/50">
                          {client.status === 'active' ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
                        </button>
                        <button onClick={e => { e.stopPropagation(); setEditClient(client); setShowForm(true); }} title="Edit" className="p-1.5 rounded-md text-[#888] hover:text-[#1A1A2E] hover:bg-white/50">
                          <Settings className="size-3.5" />
                        </button>
                        {onViewCustomer && client.tenant_id && (
                          <button onClick={e => { e.stopPropagation(); onViewCustomer(client.tenant_id); }} title="View Detail" className="p-1.5 rounded-md text-[#888] hover:text-[#D4AF37] hover:bg-[#D4AF37]/10" data-testid={`view-customer-${client.id}`}>
                            <BarChart3 className="size-3.5" />
                          </button>
                        )}
                        {(client.business_id || client.contact_email) && (
                          <a
                            href={`/admin/customer/${encodeURIComponent(client.business_id || client.contact_email)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            title="360° View"
                            data-testid={`c360-open-${client.id}`}
                            className="p-1.5 rounded-md text-[#888] hover:text-[#D4AF37] hover:bg-[#D4AF37]/10 inline-flex items-center"
                          >
                            <Globe className="size-3.5" />
                          </a>
                        )}
                        <button onClick={e => { e.stopPropagation(); setServicesPopupClient(client); }}
                          title="View Active AUREM Services"
                          data-testid={`view-services-${client.id}`}
                          className="p-1.5 rounded-md text-[#888] hover:text-[#D4AF37] hover:bg-[#D4AF37]/10">
                          <Package className="size-3.5" />
                        </button>
                        <button onClick={e => { e.stopPropagation(); handleDelete(client.id); }} title="Delete" className="p-1.5 rounded-md text-[#555] hover:text-[#ef4444] hover:bg-[#ef4444]/10">
                          <Trash2 className="size-3.5" />
                        </button>
                        <div className="relative">
                          <button onClick={e => { e.stopPropagation(); setReportDropdown(reportDropdown === client.id ? null : client.id); }}
                            title="Generate Report" data-testid={`generate-report-btn-${client.id}`}
                            className="p-1.5 rounded-md text-[#888] hover:text-[#D4AF37] hover:bg-[#D4AF37]/10">
                            {generatingReport === client.id ? <Loader2 className="size-3.5 animate-spin text-[#D4AF37]" /> : <FileText className="size-3.5" />}
                          </button>
                          {reportDropdown === client.id && (
                            <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-[#FF6B00]/20 rounded-lg shadow-lg py-1 min-w-[160px]" data-testid="report-format-dropdown">
                              {[
                                { fmt: 'docx', label: 'Proposal (Word)', icon: '📄' },
                                { fmt: 'pptx', label: 'Health Deck (PPT)', icon: '📊' },
                                { fmt: 'pdf', label: 'Campaign Report (PDF)', icon: '📋' },
                              ].map(opt => (
                                <button key={opt.fmt} onClick={e => { e.stopPropagation(); generateReport(client, opt.fmt); }}
                                  data-testid={`report-${opt.fmt}-${client.id}`}
                                  className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-[#1A1A2E] hover:bg-[#D4AF37]/10 text-left">
                                  <span>{opt.icon}</span>{opt.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                      {isExpanded ? <ChevronDown className="size-4 text-[#555]" /> : <ChevronRight className="size-4 text-[#555]" />}
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-[#FF6B00]/20 pt-4">
                      <div className="grid grid-cols-3 gap-4">
                        {/* Contact */}
                        <div className="p-3 bg-white/60 rounded-lg">
                          <h4 className="text-[10px] text-[#555] tracking-wider mb-2">CONTACT</h4>
                          {client.contact_email && <p className="text-[10px] text-[#1A1A2E] flex items-center gap-1.5 mb-1"><Mail className="size-3 text-[#888]" />{client.contact_email}</p>}
                          {client.contact_phone && <p className="text-[10px] text-[#1A1A2E] flex items-center gap-1.5 mb-1"><Phone className="size-3 text-[#888]" />{client.contact_phone}</p>}
                          {client.website && <a href={client.website} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#D4AF37] flex items-center gap-1.5 hover:underline"><Globe className="size-3" />{client.website}</a>}
                        </div>
                        {/* Channels */}
                        <div className="p-3 bg-white/60 rounded-lg">
                          <h4 className="text-[10px] text-[#555] tracking-wider mb-2">ACTIVE CHANNELS</h4>
                          <div className="space-y-1">
                            {client.gmail_email && <p className="text-[10px] text-[#1A1A2E] flex items-center gap-1.5"><Mail className="size-3 text-[#EA4335]" />{client.gmail_email}</p>}
                            {client.whatsapp_number && <p className="text-[10px] text-[#1A1A2E] flex items-center gap-1.5"><MessageCircle className="size-3 text-[#25D366]" />+{client.whatsapp_number}</p>}
                            {client.sms_phone && <p className="text-[10px] text-[#1A1A2E] flex items-center gap-1.5"><Smartphone className="size-3 text-[#f59e0b]" />{client.sms_phone} ({client.sms_carrier})</p>}
                          </div>
                        </div>
                        {/* Campaign */}
                        <div className="p-3 bg-white/60 rounded-lg">
                          <h4 className="text-[10px] text-[#555] tracking-wider mb-2">CAMPAIGN</h4>
                          {client.brand_tagline && <p className="text-[10px] text-[#1A1A2E] mb-1">{client.brand_tagline}</p>}
                          {client.default_discount && <p className="text-[10px] text-[#D4AF37]">{client.default_discount}% default discount</p>}
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-[9px] text-[#555]">Security:</span>
                            {client.has_gmail_password && <span className="text-[9px] px-1.5 py-0.5 bg-[#4ade80]/10 text-[#4ade80] rounded flex items-center gap-1"><Shield className="size-2.5" /> Gmail</span>}
                            {client.has_meta_token && <span className="text-[9px] px-1.5 py-0.5 bg-[#25D366]/10 text-[#25D366] rounded flex items-center gap-1"><Shield className="size-2.5" /> Meta</span>}
                          </div>
                        </div>
                      </div>
                      {/* Social Media Row */}
                      {(client.instagram_handle || client.facebook_page_id || client.youtube_channel || client.linkedin_url || client.twitter_handle) && (
                        <div className="mt-3 p-3 bg-white/60 rounded-lg">
                          <h4 className="text-[10px] text-[#555] tracking-wider mb-2">SOCIAL MEDIA</h4>
                          <div className="flex flex-wrap gap-2">
                            {client.instagram_handle && <span className="text-[10px] px-2 py-1 bg-[#E4405F]/10 text-[#E4405F] rounded flex items-center gap-1"><Instagram className="size-3" />{client.instagram_handle}</span>}
                            {client.facebook_page_id && <span className="text-[10px] px-2 py-1 bg-[#1877F2]/10 text-[#1877F2] rounded flex items-center gap-1"><Facebook className="size-3" />{client.facebook_page_id}</span>}
                            {client.youtube_channel && <span className="text-[10px] px-2 py-1 bg-[#FF0000]/10 text-[#FF0000] rounded flex items-center gap-1"><Youtube className="size-3" />YouTube</span>}
                            {client.linkedin_url && <span className="text-[10px] px-2 py-1 bg-[#0A66C2]/10 text-[#0A66C2] rounded flex items-center gap-1"><Linkedin className="size-3" />LinkedIn</span>}
                            {client.twitter_handle && <span className="text-[10px] px-2 py-1 bg-[#999]/10 text-[#999] rounded flex items-center gap-1"><Twitter className="size-3" />{client.twitter_handle}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="p-16 bg-white/80 backdrop-blur-sm border border-[#FF6B00]/20 rounded-xl text-center">
            <Users className="size-12 text-[#333] mx-auto mb-4" />
            <h3 className="text-sm font-medium text-[#1A1A2E] mb-2">No clients yet</h3>
            <p className="text-[11px] text-[#5a5a72] mb-6">Add your first business client to start managing their automation</p>
            <button onClick={() => { setEditClient(null); setShowForm(true); }} data-testid="add-first-client-btn" className="px-5 py-2.5 text-xs font-semibold text-[#050505] bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg hover:opacity-90">
              Add First Client
            </button>
          </div>
        )}
      </div>

      {/* Client Form Modal */}
      {showForm && (
        <ClientForm
          client={editClient}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditClient(null); }}
          saving={saving}
        />
      )}

      {/* Admin Password Reset Modal — two-step: confirm → result */}
      {resetTarget && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          data-testid="reset-password-modal"
          onClick={closeResetModal}
        >
          <div
            className="w-full max-w-md bg-[#0F0F10] border border-[#D4AF37]/30 rounded-xl p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {!resetResult ? (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="size-10 rounded-lg bg-[#ef4444]/15 flex items-center justify-center text-xl">🔑</div>
                  <div>
                    <h3 className="text-base font-semibold text-[#F5E6C8]">Reset Password</h3>
                    <p className="text-xs text-[#B8AE9F]">{resetTarget.email}</p>
                  </div>
                </div>
                <label className="block text-xs text-[#B8AE9F] mb-2 uppercase tracking-wider">
                  New Password (leave blank to auto-generate secure 14-char password)
                </label>
                <input
                  type="text"
                  value={resetInput}
                  onChange={(e) => setResetInput(e.target.value)}
                  placeholder="auto-generate"
                  className="w-full px-3 py-2.5 bg-[#050505] border border-[#2a2a2a] rounded text-sm text-[#F5E6C8] placeholder-[#555] focus:border-[#D4AF37]/60 outline-none mb-4"
                  data-testid="reset-password-input"
                  autoFocus
                />
                <div className="p-3 mb-4 rounded bg-[#ef4444]/10 border border-[#ef4444]/30 text-xs text-[#F5E6C8]">
                  ⚠ This will immediately invalidate the user's current password. Share the new one over a trusted channel (WhatsApp/SMS).
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={closeResetModal}
                    className="flex-1 py-2 rounded bg-white/5 text-[#B8AE9F] text-sm hover:bg-white/10"
                    data-testid="reset-cancel-btn"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={submitPasswordReset}
                    disabled={resetBusy}
                    className="flex-1 py-2 rounded bg-[#D4AF37] text-[#050505] font-semibold text-sm hover:bg-[#e2c97e] disabled:opacity-50"
                    data-testid="reset-confirm-btn"
                  >
                    {resetBusy ? 'Resetting…' : 'Reset Password'}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="size-10 rounded-lg bg-[#4ADE80]/15 flex items-center justify-center text-xl">✓</div>
                  <div>
                    <h3 className="text-base font-semibold text-[#F5E6C8]">Password Reset</h3>
                    <p className="text-xs text-[#B8AE9F]">{resetResult.email}</p>
                  </div>
                </div>
                <label className="block text-xs text-[#B8AE9F] mb-2 uppercase tracking-wider">
                  New Password {resetResult.generated && <span className="text-[#4ADE80]">(auto-generated)</span>}
                </label>
                <div className="flex gap-2 mb-4">
                  <input
                    type="text"
                    readOnly
                    value={resetResult.new_password}
                    className="flex-1 px-3 py-2.5 bg-[#050505] border border-[#D4AF37]/40 rounded font-mono text-sm text-[#D4AF37]"
                    data-testid="reset-new-password-display"
                    onFocus={(e) => e.target.select()}
                  />
                  <button
                    onClick={() => {
                      navigator.clipboard?.writeText(resetResult.new_password);
                      alert('Copied to clipboard');
                    }}
                    className="px-3 py-2 rounded bg-[#D4AF37]/20 text-[#D4AF37] text-xs font-semibold hover:bg-[#D4AF37]/30"
                    data-testid="reset-copy-btn"
                  >
                    📋 Copy
                  </button>
                </div>
                <div className="p-3 mb-4 rounded bg-[#D4AF37]/10 border border-[#D4AF37]/30 text-xs text-[#F5E6C8]">
                  ⚠ This password is shown ONCE. Copy it now, it will not be retrievable again. Share with the user over WhatsApp or SMS.
                </div>
                <button
                  onClick={closeResetModal}
                  className="w-full py-2 rounded bg-[#D4AF37] text-[#050505] font-semibold text-sm hover:bg-[#e2c97e]"
                  data-testid="reset-done-btn"
                >
                  Done
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Customer Services Popup (auto-polling live view) */}
      {servicesPopupClient && (
        <CustomerServicesPopup
          customer={servicesPopupClient}
          token={token}
          onClose={() => setServicesPopupClient(null)}
        />
      )}
    </div>
  );
}
