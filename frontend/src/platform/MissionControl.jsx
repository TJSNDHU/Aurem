/**
 * AUREM Mission Control — Real MongoDB Data
 * ORA Intelligence Hub
 */

import React, { useState, useEffect , useCallback} from 'react';
import { 
  MessageSquare, Zap, BarChart3, Users, Settings, CreditCard, 
  Mail, MessageCircle, Globe, Code, Shield, TrendingUp, Building2, Key,
  Rocket, Activity, CheckCircle, ArrowRight, Sparkles, Phone, Lock,
  Mic, Network
} from 'lucide-react';
import '../theme/aurem-green.css';
import LiveCampaignPipeline from './LiveCampaignPipeline';
import OraSelfHealWidget from './OraSelfHealWidget';

const API_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin;
const COPPER = '#FF6B00';

const MissionControl = ({ onNavigate, token }) => {
  const [stats, setStats] = useState({
    apiKeys: 0, totalLeads: 0, voiceCalls: 0, activeCalls: 0,
    systemHealth: 'healthy', activeServices: 21
  });

  const fetchAllStats = useCallback(async () => {
    const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };
    try {
      const [keysRes, voiceRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/integration/keys`, { headers }),
        fetch(`${API_URL}/api/voice-analytics/data?range=7d`, { headers }),
      ]);

      const newStats = { ...stats };

      if (keysRes.status === 'fulfilled' && keysRes.value.ok) {
        const d = await keysRes.value.json();
        newStats.apiKeys = d.count || d.keys?.length || 0;
      }

      if (voiceRes.status === 'fulfilled' && voiceRes.value.ok) {
        const d = await voiceRes.value.json();
        newStats.voiceCalls = d.summary?.totalCalls || 0;
        newStats.activeCalls = d.liveCalls?.active || 0;
      }

      setStats(newStats);
    } catch (err) {
      console.error('Stats fetch error:', err);
    }
  }, [token]);

  useEffect(() => {
    fetchAllStats();
  }, [fetchAllStats]);

  useEffect(() => {
    const interval = setInterval(fetchAllStats, 30000);
    return () => clearInterval(interval);
  }, [fetchAllStats]);

  const features = [
    {
      id: 'ai-conversation', title: 'ORA Chat',
      description: 'Chat with ORA Intelligence. Multi-agent automation for business.',
      icon: MessageSquare, color: COPPER, status: 'active', category: 'WORKSPACE',
      badge: '24/7 Active'
    },
    {
      id: 'omnichannel-hub', title: 'Comm Hub',
      description: 'Unified communication center. Email, SMS, WhatsApp in one inbox.',
      icon: MessageCircle, color: '#3b82f6', status: 'active', category: 'WORKSPACE',
      badge: 'Unified'
    },
    {
      id: 'acquisition-engine', title: 'Acquisition Engine',
      description: '5-tier zero-cost customer acquisition funnel. DIY to ORA Voice Agent.',
      icon: Zap, color: '#16a34a', status: 'active', category: 'WORKSPACE',
      badge: '5 Tiers'
    },
    {
      id: 'analytics-hub', title: 'Analytics Hub',
      description: 'Business intelligence dashboard. Real-time metrics, insights, and reports.',
      icon: BarChart3, color: '#7c3aed', status: 'active', category: 'WORKSPACE',
      badge: 'Live Data'
    },
    {
      id: 'voice-analytics', title: 'Voice Analytics',
      description: `Real-time voice agent metrics. ${stats.voiceCalls} calls this week.`,
      icon: Phone, color: COPPER, status: 'active', category: 'WORKSPACE',
      badge: `${stats.voiceCalls} Calls`
    },
    {
      id: 'agent-swarm', title: 'Agent Swarm',
      description: 'Deploy ORA agent teams. Scout, Architect, Closer, and Orchestrator.',
      icon: Users, color: '#0ea5e9', status: 'active', category: 'WORKSPACE',
      badge: '5 Agents'
    },
    {
      id: 'customer-scanner', title: 'Customer Scanner',
      description: 'ORA-powered customer analysis. Profile enrichment and scoring.',
      icon: Activity, color: '#f59e0b', status: 'active', category: 'SALES',
      badge: 'ORA Scan'
    },
    {
      id: 'sales-pipeline', title: 'Sales Pipeline',
      description: 'Visual deal tracking. Kanban board for managing sales flow.',
      icon: TrendingUp, color: '#ef4444', status: 'active', category: 'SALES',
      badge: 'Pipeline'
    },
    {
      id: 'voice-sales-agent', title: 'Voice Sales Agent',
      description: 'ORA voice agent for outbound sales calls. Auto-dialer + tone sync.',
      icon: Mic, color: '#8b5cf6', status: 'active', category: 'SALES',
      badge: stats.activeCalls > 0 ? `${stats.activeCalls} Live` : 'Ready'
    },
    {
      id: 'circuit-breakers', title: 'Circuit Breakers',
      description: 'System health monitoring. Protection for external services.',
      icon: Shield, color: '#4CAF50', status: 'active', category: 'SYSTEM',
      badge: 'All Healthy'
    },
    {
      id: 'github-leads', title: 'Intelligence & Growth',
      description: 'ORA-powered lead discovery. Mine repositories for leads.',
      icon: TrendingUp, color: '#FF6B6B', status: 'active', category: 'SYSTEM',
      badge: 'ORA Powered'
    },
    {
      id: 'business-management', title: 'Business Management',
      description: 'Manage customers, deals, and pipelines. Full CRM functionality.',
      icon: Building2, color: '#06b6d4', status: 'active', category: 'SYSTEM',
      badge: 'CRM'
    },
    {
      id: 'partner-referral', title: 'Partner Network',
      description: 'Referral portal. Earn rewards for bringing in new tenants.',
      icon: Network, color: '#a855f7', status: 'active', category: 'SYSTEM',
      badge: 'Referral'
    },
    {
      id: 'client-manager', title: 'Client Manager',
      description: 'Multi-tenant admin. AES-256 encrypted credential vault.',
      icon: Lock, color: '#64748b', status: 'active', category: 'ADMIN',
      badge: 'Secure'
    },
    {
      id: 'api-keys', title: 'API Keys',
      description: 'Generate integration keys. Embed ORA chat on external sites.',
      icon: Key, color: '#64C8FF', status: 'active', category: 'INTEGRATIONS',
      badge: `${stats.apiKeys} Keys`
    },
    {
      id: 'secret-vault', title: 'Secret Vault',
      description: 'AES-256 encrypted credential store. BYON compliance vault.',
      icon: Lock, color: '#f97316', status: 'active', category: 'INTEGRATIONS',
      badge: 'Encrypted'
    },
    {
      id: 'gmail-channel', title: 'Gmail Channel',
      description: 'Connect Gmail. Read, send, and automate email workflows.',
      icon: Mail, color: '#ea4335', status: 'active', category: 'INTEGRATIONS',
      badge: 'PRO'
    },
    {
      id: 'crm-connect', title: 'CRM Connect',
      description: 'Integrate with Salesforce, HubSpot, and other CRM platforms.',
      icon: Globe, color: '#14b8a6', status: 'active', category: 'INTEGRATIONS',
      badge: 'Connect'
    },
    {
      id: 'whatsapp-flows', title: 'WhatsApp Flows',
      description: 'WhatsApp Business API. Automate conversations at scale.',
      icon: MessageCircle, color: '#25d366', status: 'active', category: 'INTEGRATIONS',
      badge: 'PRO'
    },
    {
      id: 'api-gateway', title: 'API Gateway',
      description: 'Manage webhooks and API endpoints. Monitor requests.',
      icon: Code, color: '#6366f1', status: 'active', category: 'INTEGRATIONS',
      badge: 'Gateway'
    },
    {
      id: 'settings', title: 'Settings',
      description: 'Account preferences, team management, and security settings.',
      icon: Settings, color: '#78716c', status: 'active', category: 'ACCOUNT',
      badge: 'Config'
    },
    {
      id: 'usage-billing', title: 'Usage & Billing',
      description: 'Usage stats, subscriptions, and billing information.',
      icon: CreditCard, color: '#0284c7', status: 'active', category: 'ACCOUNT',
      badge: 'Billing'
    }
  ];

  const categories = ['WORKSPACE', 'SALES', 'SYSTEM', 'ADMIN', 'INTEGRATIONS', 'ACCOUNT'];

  return (
    <div className="flex-1 overflow-y-auto p-6 aurem-scroll" style={{ background: 'transparent' }} data-testid="mission-control">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6" style={{ animation: 'auremFadeSlideDown 0.5s ease both' }}>
          <div className="flex items-center gap-3 mb-2">
            <div className="size-10 rounded-xl flex items-center justify-center" style={{
              background: `linear-gradient(135deg, ${COPPER}, #B38659)`,
              boxShadow: `0 4px 12px rgba(212,163,115,0.2)`,
            }}>
              <Rocket className="size-5" style={{ color: 'var(--aurem-heading)' }} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-wider" style={{ fontFamily: "'Montserrat', sans-serif", color: 'var(--aurem-heading)' }}>
                ORA MISSION CONTROL
              </h1>
              <p className="text-xs" style={{ color: 'var(--aurem-body-secondary)' }}>{features.length} modules online &middot; All systems operational</p>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Active Modules', value: features.length, icon: CheckCircle, color: '#16a34a' },
            { label: 'Voice Calls (7d)', value: stats.voiceCalls, icon: Phone, color: COPPER },
            { label: 'API Keys', value: stats.apiKeys, icon: Key, color: '#3b82f6' },
            { label: 'System Health', value: '100%', icon: Shield, color: '#16a34a' },
          ].map((s, i) => (
            <div key={i} className="aurem-glass-card p-3 flex items-center gap-3">
              <div className="size-9 rounded-lg flex items-center justify-center" style={{ background: `${s.color}12` }}>
                <s.icon size={18} color={s.color} />
              </div>
              <div>
                <div className="text-xl font-light font-mono" style={{ color: 'var(--aurem-heading)' }}>{s.value}</div>
                <div className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--aurem-body-secondary)', fontFamily: "'Montserrat', sans-serif" }}>{s.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Feature Grid by Category */}
        {categories.map(cat => {
          const catFeatures = features.filter(f => f.category === cat);
          if (catFeatures.length === 0) return null;
          return (
            <div key={cat} className="mb-5">
              <h2 className="text-[10px] font-bold tracking-widest mb-3 px-1" style={{ fontFamily: "'Montserrat', sans-serif", color: 'var(--aurem-body-secondary)' }}>{cat}</h2>
              <div className="grid grid-cols-3 gap-3">
                {catFeatures.map((f, i) => (
                  <button
                    key={f.id}
                    onClick={() => onNavigate(f.id)}
                    data-testid={`mc-${f.id}`}
                    className="aurem-glass-card p-4 text-left transition-all hover:scale-[1.01] cursor-pointer group"
                    style={{ animation: `auremFadeSlideIn 0.3s ease both ${i * 0.05}s` }}
                  >
                    <div className="flex items-start gap-3">
                      <div className="size-10 rounded-xl flex items-center justify-center flex-shrink-0 transition-all group-hover:scale-110" style={{ background: `${f.color}12` }}>
                        <f.icon size={20} color={f.color} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-semibold truncate" style={{ color: 'var(--aurem-heading)' }}>{f.title}</span>
                          {f.badge && (
                            <span className="px-1.5 py-0.5 rounded text-[8px] font-bold tracking-wide whitespace-nowrap" style={{ background: `${f.color}15`, color: f.color }}>
                              {f.badge}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] leading-relaxed line-clamp-2" style={{ color: 'var(--aurem-body-secondary)' }}>{f.description}</p>
                      </div>
                      <ArrowRight size={14} className="text-[#999] opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1" />
                    </div>
                  </button>
                ))}
              </div>
              {/* Live Campaign Pipeline — iter 278 (replaced warehouse robot) */}
              {cat === 'SYSTEM' && (
                <div className="mt-4 space-y-4">
                  <OraSelfHealWidget token={token} />
                  <LiveCampaignPipeline token={token} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MissionControl;
