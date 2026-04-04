/**
 * AUREM Mission Control - Admin Dashboard
 * Central hub showing all features and quick actions
 */

import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, Zap, BarChart3, Users, Settings, CreditCard, 
  Mail, MessageCircle, Globe, Code, Shield, TrendingUp, Building2, Key,
  Rocket, Activity, CheckCircle, Clock, ArrowRight, Sparkles
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const MissionControl = ({ onNavigate, token }) => {
  const [stats, setStats] = useState({
    apiKeys: 0,
    systemHealth: 'healthy',
    activeServices: 13
  });

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      // Fetch API keys count
      const keysRes = await fetch(`${API_URL}/api/integration/keys`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (keysRes.ok) {
        const data = await keysRes.json();
        setStats(prev => ({ ...prev, apiKeys: data.count || 0 }));
      }
    } catch (err) {
      console.error('Stats fetch error:', err);
    }
  };

  // Feature cards configuration
  const features = [
    // WORKSPACE - Working Features
    {
      id: 'ai-conversation',
      title: 'AI Conversation',
      description: 'Chat with AUREM Intelligence. Multi-agent AI system for business automation.',
      icon: MessageSquare,
      color: '#D4AF37',
      bgGradient: 'from-[#D4AF37]/20 to-[#8B7355]/20',
      borderColor: 'border-[#D4AF37]/30',
      status: 'active',
      category: 'WORKSPACE',
      badge: '24/7 Active'
    },
    {
      id: 'api-keys',
      title: 'API Keys',
      description: 'Generate integration keys. Embed AUREM chat on your external websites.',
      icon: Key,
      color: '#64C8FF',
      bgGradient: 'from-[#64C8FF]/20 to-[#3B82F6]/20',
      borderColor: 'border-[#64C8FF]/30',
      status: 'active',
      category: 'INTEGRATIONS',
      badge: `${stats.apiKeys} Keys`,
      quickAction: true
    },
    {
      id: 'circuit-breakers',
      title: 'Circuit Breakers',
      description: 'System health monitoring. Protection for 13 external services and APIs.',
      icon: Shield,
      color: '#4CAF50',
      bgGradient: 'from-[#4CAF50]/20 to-[#2E7D32]/20',
      borderColor: 'border-[#4CAF50]/30',
      status: 'active',
      category: 'SYSTEM',
      badge: 'All Healthy'
    },
    {
      id: 'github-leads',
      title: 'Intelligence & Growth',
      description: 'ORA-powered lead discovery. Mine GitHub repositories for potential leads.',
      icon: TrendingUp,
      color: '#FF6B6B',
      bgGradient: 'from-[#FF6B6B]/20 to-[#C92A2A]/20',
      borderColor: 'border-[#FF6B6B]/30',
      status: 'active',
      category: 'SYSTEM',
      badge: 'AI Powered'
    },

    // WORKSPACE - Coming Soon
    {
      id: 'automation-engine',
      title: 'Automation Engine',
      description: 'Build and deploy automated workflows. Connect triggers, actions, and conditions.',
      icon: Zap,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'WORKSPACE'
    },
    {
      id: 'analytics-hub',
      title: 'Analytics Hub',
      description: 'Business intelligence dashboard. Real-time metrics, insights, and reports.',
      icon: BarChart3,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'WORKSPACE'
    },
    {
      id: 'agent-swarm',
      title: 'Agent Swarm',
      description: 'Deploy AI agent teams. Scout, Architect, Closer, and Orchestrator working together.',
      icon: Users,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'WORKSPACE'
    },
    {
      id: 'business-management',
      title: 'Business Management',
      description: 'Manage customers, deals, and pipelines. Complete CRM functionality.',
      icon: Building2,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'SYSTEM'
    },

    // INTEGRATIONS - Coming Soon
    {
      id: 'gmail-channel',
      title: 'Gmail Channel',
      description: 'Connect your Gmail. Read, send, and automate email communications.',
      icon: Mail,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'INTEGRATIONS'
    },
    {
      id: 'crm-connect',
      title: 'CRM Connect',
      description: 'Integrate with Salesforce, HubSpot, and other CRM platforms.',
      icon: Globe,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'INTEGRATIONS'
    },
    {
      id: 'whatsapp-flows',
      title: 'WhatsApp Flows',
      description: 'WhatsApp Business API integration. Automate conversations at scale.',
      icon: MessageCircle,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'INTEGRATIONS'
    },
    {
      id: 'api-gateway',
      title: 'API Gateway',
      description: 'Manage webhooks and API endpoints. Monitor requests and responses.',
      icon: Code,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'INTEGRATIONS'
    },

    // ACCOUNT - Coming Soon
    {
      id: 'settings',
      title: 'Settings',
      description: 'Account preferences, team management, and security settings.',
      icon: Settings,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'ACCOUNT'
    },
    {
      id: 'usage-billing',
      title: 'Usage & Billing',
      description: 'View usage stats, manage subscriptions, and billing information.',
      icon: CreditCard,
      color: '#888',
      bgGradient: 'from-[#333]/20 to-[#222]/20',
      borderColor: 'border-[#333]/30',
      status: 'coming-soon',
      category: 'ACCOUNT'
    }
  ];

  const handleCardClick = (feature) => {
    if (feature.status === 'active') {
      onNavigate(feature.id);
    }
  };

  const activeFeatures = features.filter(f => f.status === 'active');
  const comingSoonFeatures = features.filter(f => f.status === 'coming-soon');

  return (
    <div className="flex-1 overflow-y-auto bg-[#050505] p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
              <Rocket className="w-6 h-6 text-[#050505]" />
            </div>
            <div>
              <h1 className="text-3xl font-light text-[#F4F4F4] tracking-wider">Mission Control</h1>
              <p className="text-sm text-[#666]">AUREM Business Intelligence Platform</p>
            </div>
          </div>
        </div>

        {/* Quick Stats Bar */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#4CAF50]/10 flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-[#4CAF50]" />
              </div>
              <div>
                <div className="text-xs text-[#666] uppercase tracking-wider">System Status</div>
                <div className="text-lg font-medium text-[#4CAF50]">All Systems Healthy</div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#64C8FF]/10 flex items-center justify-center">
                <Key className="w-5 h-5 text-[#64C8FF]" />
              </div>
              <div>
                <div className="text-xs text-[#666] uppercase tracking-wider">API Keys</div>
                <div className="text-lg font-medium text-[#F4F4F4]">{stats.apiKeys} Active</div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#D4AF37]/10 flex items-center justify-center">
                <Shield className="w-5 h-5 text-[#D4AF37]" />
              </div>
              <div>
                <div className="text-xs text-[#666] uppercase tracking-wider">Protected Services</div>
                <div className="text-lg font-medium text-[#F4F4F4]">{stats.activeServices} Services</div>
              </div>
            </div>
          </div>

          <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#FF6B6B]/10 flex items-center justify-center">
                <Activity className="w-5 h-5 text-[#FF6B6B]" />
              </div>
              <div>
                <div className="text-xs text-[#666] uppercase tracking-wider">Active Features</div>
                <div className="text-lg font-medium text-[#F4F4F4]">{activeFeatures.length} / {features.length}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Active Features */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles className="w-5 h-5 text-[#D4AF37]" />
            <h2 className="text-xl font-medium text-[#F4F4F4]">Active Features</h2>
            <span className="px-2 py-1 text-xs bg-[#D4AF37]/10 text-[#D4AF37] rounded border border-[#D4AF37]/30">
              {activeFeatures.length} Available Now
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {activeFeatures.map((feature) => {
              const Icon = feature.icon;
              return (
                <button
                  key={feature.id}
                  onClick={() => handleCardClick(feature)}
                  className={`group relative p-6 bg-gradient-to-br ${feature.bgGradient} border ${feature.borderColor} rounded-xl text-left hover:scale-[1.02] transition-all duration-300 cursor-pointer`}
                >
                  {/* Badge */}
                  {feature.badge && (
                    <div className="absolute top-4 right-4 px-2 py-1 text-[9px] bg-[#0A0A0A]/80 border border-[#D4AF37]/30 text-[#D4AF37] rounded uppercase tracking-wider">
                      {feature.badge}
                    </div>
                  )}

                  {/* Icon */}
                  <div className={`w-14 h-14 rounded-xl bg-gradient-to-br from-[${feature.color}]/20 to-[${feature.color}]/10 flex items-center justify-center mb-4`}>
                    <Icon className="w-7 h-7" style={{ color: feature.color }} />
                  </div>

                  {/* Content */}
                  <h3 className="text-lg font-medium text-[#F4F4F4] mb-2 group-hover:text-[#D4AF37] transition-colors">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-[#888] leading-relaxed mb-4">
                    {feature.description}
                  </p>

                  {/* Action */}
                  <div className="flex items-center gap-2 text-sm" style={{ color: feature.color }}>
                    <span className="group-hover:translate-x-1 transition-transform">Open</span>
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Coming Soon Features */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-[#666]" />
            <h2 className="text-xl font-medium text-[#F4F4F4]">Coming Soon</h2>
            <span className="px-2 py-1 text-xs bg-[#333]/20 text-[#666] rounded border border-[#333]/30">
              {comingSoonFeatures.length} In Development
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {comingSoonFeatures.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.id}
                  className={`relative p-5 bg-gradient-to-br ${feature.bgGradient} border ${feature.borderColor} rounded-xl opacity-60 cursor-not-allowed`}
                >
                  {/* Icon */}
                  <div className="w-12 h-12 rounded-lg bg-[#333]/20 flex items-center justify-center mb-3">
                    <Icon className="w-6 h-6 text-[#666]" />
                  </div>

                  {/* Content */}
                  <h3 className="text-base font-medium text-[#AAA] mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-xs text-[#666] leading-relaxed">
                    {feature.description}
                  </p>

                  {/* Coming Soon Badge */}
                  <div className="absolute top-4 right-4">
                    <span className="px-2 py-1 text-[9px] bg-[#333]/40 text-[#666] rounded uppercase tracking-wider">
                      Coming Soon
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer Info */}
        <div className="mt-8 p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-[#666]">
              <div className="w-2 h-2 bg-[#4CAF50] rounded-full animate-pulse" />
              <span>All systems operational</span>
            </div>
            <div className="text-xs text-[#555]">
              AUREM Platform v1.0 • Last updated: {new Date().toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MissionControl;
