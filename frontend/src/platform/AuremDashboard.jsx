/**
 * AUREM Intelligence Dashboard
 * Complete AI Platform Interface
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  MessageSquare, Zap, BarChart3, Users, Settings, CreditCard, 
  Mail, MessageCircle, Globe, Send, Mic, MicOff,
  Sparkles, Activity, Brain, Rocket, Shield, Code, LogOut,
  ChevronRight, Plus, Play, Pause, RefreshCw, Check, X,
  TrendingUp, Clock, Target, Phone, PhoneCall, Building2, Key
} from 'lucide-react';

// Voice component
import AuremVoice from '../components/AuremVoice';
// System status bar
import SystemStatusBar from '../components/SystemStatusBar';
// Circuit breaker dashboard
import CircuitBreakerDashboard from '../components/CircuitBreakerDashboard';
// ORA Voice Wake-Word (Floating)
import VoiceWakeWord from '../components/VoiceWakeWord';
// ORA Forensic Uploader (Floating)
import ForensicUploader from '../components/ForensicUploader';
// GitHub Lead Miner
import GitHubLeadMiner from '../components/GitHubLeadMiner';
// API Keys Manager
import APIKeysManager from './APIKeysManager';
// Mission Control Dashboard
import MissionControl from './MissionControl';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════════════════════
// SIDEBAR COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

const Sidebar = ({ activeItem, onItemClick, user, onLogout }) => {
  const navSections = [
    {
      title: 'WORKSPACE',
      items: [
        { id: 'ai-conversation', label: 'AI Conversation', icon: MessageSquare },
        { id: 'automation-engine', label: 'Automation Engine', icon: Zap },
        { id: 'analytics-hub', label: 'Analytics Hub', icon: BarChart3 },
        { id: 'agent-swarm', label: 'Agent Swarm', icon: Users },
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { id: 'customer-scanner', label: 'Customer Scanner', icon: Activity },
        { id: 'circuit-breakers', label: 'Circuit Breakers', icon: Shield },
        { id: 'github-leads', label: 'Intelligence & Growth', icon: TrendingUp },
        { id: 'business-management', label: 'Business Management', icon: Building2 },
      ]
    },
    {
      title: 'INTEGRATIONS',
      items: [
        { id: 'api-keys', label: 'API Keys', icon: Key },
        { id: 'gmail-channel', label: 'Gmail Channel', icon: Mail },
        { id: 'crm-connect', label: 'CRM Connect', icon: Globe },
        { id: 'whatsapp-flows', label: 'WhatsApp Flows', icon: MessageCircle },
        { id: 'api-gateway', label: 'API Gateway', icon: Code },
      ]
    },
    {
      title: 'ACCOUNT',
      items: [
        { id: 'settings', label: 'Settings', icon: Settings },
        { id: 'usage-billing', label: 'Usage & Billing', icon: CreditCard },
      ]
    }
  ];

  return (
    <aside className="w-56 h-screen bg-[#0A0A0A] border-r border-[#1A1A1A] flex flex-col" data-testid="sidebar">
      {/* Logo */}
      <div className="p-4 border-b border-[#1A1A1A]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-[#050505]" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-[#D4AF37] tracking-wider">AUREM</h1>
            <p className="text-[10px] text-[#666] tracking-wide">BUSINESS AI PLATFORM</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4">
        {navSections.map((section, idx) => (
          <div key={idx} className="mb-6">
            <h3 className="px-4 mb-2 text-[10px] font-medium text-[#555] tracking-wider">
              {section.title}
            </h3>
            <ul className="space-y-1 px-2">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeItem === item.id;
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => onItemClick(item.id)}
                      data-testid={`nav-${item.id}`}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all ${
                        isActive 
                          ? 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30' 
                          : 'text-[#888] hover:text-[#CCC] hover:bg-[#151515]'
                      }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <span>{item.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User & Logout */}
      <div className="p-4 border-t border-[#1A1A1A]">
        <div className="text-xs text-[#666] mb-3">
          {user?.email || 'admin@aurem.live'}
        </div>
        <button
          onClick={onLogout}
          data-testid="logout-btn"
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[#666] hover:text-[#D4AF37] hover:bg-[#151515] transition-all"
        >
          <LogOut className="w-4 h-4" />
          <span>Disconnect</span>
        </button>
        <div className="mt-3 flex items-center gap-2 text-xs text-[#4A4]">
          <div className="w-2 h-2 bg-[#4A4] rounded-full animate-pulse" />
          <span>ALL SYSTEMS OPERATIONAL</span>
        </div>
      </div>
    </aside>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// RIGHT PANEL - METRICS
// ═══════════════════════════════════════════════════════════════════════════════

const MetricsPanel = ({ metrics }) => {
  const displayMetrics = [
    { label: 'QUERIES TODAY', value: metrics?.queries_today || '2,848', color: '#D4AF37' },
    { label: 'UPTIME', value: `${metrics?.uptime || 98.4}%`, color: '#4A4' },
    { label: 'AVG RESPONSE', value: `${metrics?.avg_response_time || 1.5}s`, color: '#D4AF37' },
    { label: 'ACTIVE BRANDS', value: metrics?.active_brands || '47', color: '#D4AF37' },
  ];

  return (
    <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#1A1A1A]">
      <h3 className="text-[10px] font-medium text-[#555] tracking-wider mb-3">PLATFORM METRICS</h3>
      <div className="grid grid-cols-2 gap-2">
        {displayMetrics.map((metric, idx) => (
          <div key={idx} className="p-2 bg-[#050505] rounded border border-[#1A1A1A]">
            <div className="text-lg font-semibold" style={{ color: metric.color }}>{metric.value}</div>
            <div className="text-[9px] text-[#666] uppercase tracking-wider">{metric.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const AgentSwarmStatus = ({ agents }) => {
  const defaultAgents = [
    { name: 'Scout Agent', status: 'SCANNING', color: '#D4AF37' },
    { name: 'Architect Agent', status: 'BUILDING', color: '#D4AF37' },
    { name: 'Envoy Agent', status: 'LIVE', color: '#4A4' },
    { name: 'Closer Agent', status: 'STANDBY', color: '#666' },
    { name: 'Orchestrator', status: 'MANAGING', color: '#4A4' },
  ];

  const displayAgents = agents || defaultAgents;

  return (
    <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#1A1A1A]">
      <h3 className="text-[10px] font-medium text-[#555] tracking-wider mb-3">AGENT SWARM STATUS</h3>
      <div className="space-y-2">
        {displayAgents.map((agent, idx) => (
          <div key={idx} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: agent.color || (agent.status === 'STANDBY' ? '#666' : '#4A4') }} 
              />
              <span className="text-[#AAA]">{agent.name}</span>
            </div>
            <span className="text-[10px] text-[#666] tracking-wider">{agent.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const CapabilitiesBadges = ({ capabilities }) => {
  const defaultCapabilities = [
    ['AUTOMATION', 'CRM AI', 'WHATSAPP'],
    ['ANALYTICS', 'MULTI-AGENT', 'VOICE AI'],
    ['API OPS', 'GROWTH', 'LLM ROUTING'],
    ['REPORTING']
  ];

  return (
    <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#1A1A1A]">
      <h3 className="text-[10px] font-medium text-[#555] tracking-wider mb-3">CAPABILITIES</h3>
      <div className="space-y-2">
        {defaultCapabilities.map((row, idx) => (
          <div key={idx} className="flex flex-wrap gap-1">
            {row.map((cap, cidx) => (
              <span key={cidx} className="px-2 py-0.5 text-[9px] bg-[#1A1A1A] text-[#888] rounded border border-[#252525]">
                {cap}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
};

const LiveActivityFeed = ({ activities }) => {
  const defaultActivities = [
    { icon: Zap, text: 'Scout completed market analysis for 3 brands', time: '2 min ago', color: '#D4AF37' },
    { icon: MessageCircle, text: 'WhatsApp flow triggered — 847 messages sent', time: '5 min ago', color: '#4A4' },
    { icon: Brain, text: 'Architect built new automation pipeline', time: '23 min ago', color: '#D4AF37' },
    { icon: Shield, text: 'Circuit breaker reset — all systems clear', time: '1 hr ago', color: '#666' },
  ];

  const displayActivities = activities || defaultActivities;

  return (
    <div className="p-3 bg-[#0A0A0A] rounded-lg border border-[#1A1A1A]">
      <h3 className="text-[10px] font-medium text-[#555] tracking-wider mb-3">LIVE ACTIVITY</h3>
      <div className="space-y-3">
        {displayActivities.map((activity, idx) => {
          const Icon = activity.icon || Activity;
          return (
            <div key={idx} className="flex gap-2 text-xs">
              <Icon className="w-4 h-4 flex-shrink-0" style={{ color: activity.color }} />
              <div>
                <p className="text-[#AAA] leading-tight">{activity.text}</p>
                <p className="text-[10px] text-[#555] mt-0.5">{activity.time}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT INTERFACE
// ═══════════════════════════════════════════════════════════════════════════════

const ChatInterface = ({ user, token }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;
    
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/aurem/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: currentInput,
          session_id: sessionId
        })
      });

      if (response.ok) {
        const data = await response.json();
        setSessionId(data.session_id);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response,
          intent: data.intent
        }]);
      } else {
        throw new Error('Chat failed');
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "I'm experiencing a connection issue. Please try again in a moment."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-[#050505]" data-testid="chat-interface">
      {/* Header */}
      <header className="px-6 py-4 border-b border-[#1A1A1A] flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-[#F4F4F4]">AUREM Intelligence</h1>
          <p className="text-xs text-[#666]">Commercial AI Platform — Multi-Agent Architecture</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#666]">AI-{Math.random().toString(36).substr(2, 6).toUpperCase()}</span>
          <button 
            onClick={() => setShowVoiceModal(true)}
            data-testid="voice-toggle"
            className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs border transition-all ${
              isVoiceEnabled 
                ? 'bg-[#D4AF37]/10 border-[#D4AF37]/30 text-[#D4AF37]' 
                : 'border-[#333] text-[#666] hover:text-[#AAA]'
            }`}
          >
            <PhoneCall className="w-3 h-3" />
            VOICE CALL
          </button>
        </div>
      </header>

      {/* Voice Modal */}
      {showVoiceModal && (
        <AuremVoice token={token} onClose={() => setShowVoiceModal(false)} />
      )}

      {/* Chat Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center">
            <div className="w-16 h-16 rounded-full bg-[#0A0A0A] border border-[#1A1A1A] flex items-center justify-center mb-6">
              <Sparkles className="w-8 h-8 text-[#D4AF37]" />
            </div>
            <h2 className="text-3xl font-light text-[#F4F4F4] tracking-wider mb-2">AUREM</h2>
            <p className="text-xs text-[#555] tracking-widest mb-8">BUSINESS INTELLIGENCE PLATFORM</p>
            <p className="text-sm text-[#888] max-w-lg mb-12">
              Your intelligent business partner. I automate operations, accelerate growth, and deploy AI systems that work while you sleep.
            </p>

            {/* Voice-to-Voice AI Section */}
            <div className="max-w-2xl w-full">
              <div className="mb-6">
                <h3 className="text-lg font-medium text-[#D4AF37] mb-2">🎤 AI Voice-to-Voice Communication</h3>
                <p className="text-sm text-[#888]">
                  Speak naturally with AUREM. Advanced voice recognition and human-like responses.
                </p>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mb-8">
                {/* Voice Call Button */}
                <button
                  onClick={() => setShowVoiceModal(true)}
                  className="group p-6 bg-gradient-to-br from-[#D4AF37]/20 to-[#8B7355]/20 border border-[#D4AF37]/30 rounded-xl hover:scale-105 transition-all"
                >
                  <div className="w-14 h-14 rounded-full bg-[#D4AF37]/20 flex items-center justify-center mx-auto mb-4 group-hover:bg-[#D4AF37]/30 transition-all">
                    <PhoneCall className="w-7 h-7 text-[#D4AF37]" />
                  </div>
                  <h4 className="text-base font-medium text-[#F4F4F4] mb-2">Start Voice Call</h4>
                  <p className="text-xs text-[#888]">Real-time AI conversation</p>
                </button>

                {/* Voice Commands */}
                <button
                  onClick={() => setShowVoiceModal(true)}
                  className="group p-6 bg-gradient-to-br from-[#64C8FF]/20 to-[#3B82F6]/20 border border-[#64C8FF]/30 rounded-xl hover:scale-105 transition-all"
                >
                  <div className="w-14 h-14 rounded-full bg-[#64C8FF]/20 flex items-center justify-center mx-auto mb-4 group-hover:bg-[#64C8FF]/30 transition-all">
                    <Mic className="w-7 h-7 text-[#64C8FF]" />
                  </div>
                  <h4 className="text-base font-medium text-[#F4F4F4] mb-2">Voice Commands</h4>
                  <p className="text-xs text-[#888]">Quick voice instructions</p>
                </button>
              </div>

              {/* Features */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-2xl mb-2">🗣️</div>
                  <p className="text-xs text-[#888]">Natural Speech</p>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-2xl mb-2">🌍</div>
                  <p className="text-xs text-[#888]">Multi-Language</p>
                </div>
                <div className="p-4 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg text-center">
                  <div className="text-2xl mb-2">⚡</div>
                  <p className="text-xs text-[#888]">Instant Response</p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-3xl mx-auto">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] p-4 rounded-lg ${
                  msg.role === 'user' 
                    ? 'bg-[#D4AF37]/10 border border-[#D4AF37]/30 text-[#F4F4F4]' 
                    : 'bg-[#0A0A0A] border border-[#1A1A1A] text-[#CCC]'
                }`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.intent && (
                    <div className="mt-2 pt-2 border-t border-[#1A1A1A]">
                      <span className="text-[10px] text-[#666]">
                        Intent: {msg.intent.intent} ({Math.round(msg.intent.confidence * 100)}%)
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-[#0A0A0A] border border-[#1A1A1A] p-4 rounded-lg">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-[#D4AF37] rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-[#D4AF37] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-[#D4AF37] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-[#1A1A1A]">
        <div className="flex items-center gap-3 bg-[#0A0A0A] border border-[#1A1A1A] rounded-lg p-2 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder="Ask AUREM anything about your business..."
            data-testid="chat-input"
            className="flex-1 bg-transparent text-[#F4F4F4] placeholder-[#555] px-3 py-2 outline-none text-sm"
          />
          <button 
            onClick={() => setIsVoiceEnabled(!isVoiceEnabled)}
            className="p-2 text-[#666] hover:text-[#D4AF37] transition-colors"
          >
            <Mic className="w-5 h-5" />
          </button>
          <button 
            onClick={handleSendMessage}
            disabled={isLoading || !input.trim()}
            data-testid="send-btn"
            className="p-2 bg-gradient-to-r from-[#D4AF37] to-[#8B7355] rounded-lg text-[#050505] hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
        <div className="flex items-center justify-center gap-4 mt-2 text-[10px] text-[#555]">
          <span>ENTER to send</span>
          <span>SHIFT+ENTER new line</span>
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

const AuremDashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [activeItem, setActiveItem] = useState('mission-control');
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(null);
  const [agents, setAgents] = useState(null);
  const [activities, setActivities] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (token) {
      fetchMetrics();
      fetchAgentStatus();
      fetchActivities();
    }
  }, [token]);

  const checkAuth = async () => {
    const storedToken = localStorage.getItem('platform_token');
    const storedUser = localStorage.getItem('platform_user');
    
    if (!storedToken) {
      navigate('/auth');
      return;
    }

    try {
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
      setToken(storedToken);
    } catch (error) {
      console.error('Auth check failed:', error);
      navigate('/auth');
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/metrics`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  };

  const fetchAgentStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/agents/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setAgents(data.agents);
      }
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    }
  };

  const fetchActivities = async () => {
    try {
      const response = await fetch(`${API_URL}/api/aurem/activity/feed`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setActivities(data.activities);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  };

  const handleNavClick = (itemId) => {
    setActiveItem(itemId);
  };

  const handleLogout = () => {
    localStorage.removeItem('platform_token');
    localStorage.removeItem('platform_user');
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-[#D4AF37] border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-[#666] text-sm">Initializing AUREM...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] flex flex-col" data-testid="aurem-dashboard">
      {/* System Status Bar */}
      <SystemStatusBar token={token} />
      
      {/* ORA Voice Wake-Word - Floating Button */}
      <VoiceWakeWord token={token} />
      
      {/* ORA Forensic Uploader - Floating Button */}
      <ForensicUploader token={token} />
      
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar 
          activeItem={activeItem} 
          onItemClick={handleNavClick}
          user={user}
          onLogout={handleLogout}
        />

        {/* Main Content Area - Dynamic based on activeItem */}
        {activeItem === 'mission-control' ? (
          <MissionControl onNavigate={handleNavClick} token={token} />
        ) : activeItem === 'customer-scanner' ? (
          <div className="flex-1 overflow-auto">
            <CustomerScanner token={token} />
          </div>
        ) : activeItem === 'circuit-breakers' ? (
          <div className="flex-1 overflow-auto">
            <CircuitBreakerDashboard token={token} />
          </div>
        ) : activeItem === 'github-leads' ? (
          <div className="flex-1 overflow-auto">
            <GitHubLeadMiner token={token} />
          </div>
        ) : activeItem === 'api-keys' ? (
          <div className="flex-1 overflow-auto">
            <APIKeysManager token={token} user={user} />
          </div>
        ) : activeItem === 'ai-conversation' ? (
          <>
            {/* Chat Interface */}
            <ChatInterface user={user} token={token} />

            {/* Right Sidebar - Metrics */}
            <aside className="w-64 border-l border-[#1A1A1A] bg-[#050505] p-4 space-y-4 overflow-y-auto">
              <MetricsPanel metrics={metrics} />
              <AgentSwarmStatus agents={agents} />
              <CapabilitiesBadges />
              <LiveActivityFeed activities={activities} />
            </aside>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-6xl mb-4">🚧</div>
              <h2 className="text-2xl font-semibold text-[#F4F4F4] mb-2">
                {activeItem.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
              </h2>
              <p className="text-[#666]">Coming soon...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuremDashboard;
