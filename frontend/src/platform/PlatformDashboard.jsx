/**
 * AUREM Command Center - Customer Dashboard
 * Company: Polaris Built Inc.
 * Theme: "Obsidian Executive" with Live Log View
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Target, Zap, Play, Settings, LogOut, LayoutGrid, Users, 
  BarChart3, Key, Webhook, ChevronRight, Check, X,
  Phone, MessageSquare, Mail, Globe, RefreshCw, Clock,
  TrendingUp, AlertCircle, CheckCircle, Loader2, Activity,
  DollarSign, Award, Eye, Radio, Brain, Crosshair, Terminal,
  Bug, Shield
} from 'lucide-react';
import AdminStatusBar from './AdminStatusBar';
import AuremBugHistory from './AuremBugHistory';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Animation variants
const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.4 } }
};

const slideIn = {
  hidden: { opacity: 0, x: -20 },
  visible: { opacity: 1, x: 0, transition: { duration: 0.3 } }
};

const PlatformDashboard = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('command');
  const [user, setUser] = useState(null);
  const [templates, setTemplates] = useState({});
  const [executions, setExecutions] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [toolsStatus, setToolsStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(null);
  
  // AUREM Vanguard state
  const [vanguardAgents, setVanguardAgents] = useState({});
  const [activeMissions, setActiveMissions] = useState([]);
  const [liveLogs, setLiveLogs] = useState([]);
  const [selectedMission, setSelectedMission] = useState(null);
  
  const logsEndRef = useRef(null);
  const token = localStorage.getItem('platform_token');

  useEffect(() => {
    if (!token) {
      navigate('/auth');
      return;
    }
    fetchAllData();
    
    // Poll for live logs
    const logInterval = setInterval(fetchLiveLogs, 2000);
    return () => clearInterval(logInterval);
  }, [token]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [liveLogs]);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const headers = { 'Authorization': `Bearer ${token}` };
      
      const [userRes, templatesRes, execRes, analyticsRes, toolsRes, agentsRes, missionsRes] = await Promise.all([
        fetch(`${API_URL}/api/platform/me`, { headers }),
        fetch(`${API_URL}/api/platform/templates`),
        fetch(`${API_URL}/api/platform/crews/executions?limit=10`, { headers }),
        fetch(`${API_URL}/api/platform/analytics?days=30`, { headers }),
        fetch(`${API_URL}/api/platform/tools/status`, { headers }),
        fetch(`${API_URL}/api/aurem/agents`),
        fetch(`${API_URL}/api/aurem/missions/active`, { headers })
      ]);

      if (userRes.ok) setUser(await userRes.json());
      else if (userRes.status === 401) {
        localStorage.removeItem('platform_token');
        navigate('/auth');
        return;
      }
      
      if (templatesRes.ok) setTemplates((await templatesRes.json()).templates || {});
      if (execRes.ok) setExecutions((await execRes.json()).executions || []);
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
      if (toolsRes.ok) setToolsStatus((await toolsRes.json()).tools || {});
      if (agentsRes.ok) setVanguardAgents((await agentsRes.json()).agents || {});
      if (missionsRes.ok) setActiveMissions((await missionsRes.json()).missions || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    }
    setLoading(false);
  };

  const fetchLiveLogs = async () => {
    try {
      const res = await fetch(`${API_URL}/api/aurem/stream/logs?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setLiveLogs(data.logs || []);
      }
    } catch (err) {}
  };

  const launchVanguard = async (industryTarget) => {
    setExecuting(industryTarget);
    try {
      const res = await fetch(`${API_URL}/api/aurem/mission/create`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
          industry_target: industryTarget,
          channels: ['email', 'whatsapp'],
          daily_limit: 50
        })
      });
      
      const data = await res.json();
      if (res.ok) {
        setSelectedMission(data.mission_id);
        fetchAllData();
      } else {
        alert(data.detail || 'Mission launch failed');
      }
    } catch (err) {
      alert('Connection error');
    }
    setExecuting(null);
  };

  const logout = () => {
    localStorage.removeItem('platform_token');
    navigate('/');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          >
            <Target className="w-10 h-10 text-[#D4AF37] mx-auto mb-4" />
          </motion.div>
          <p className="text-[#444] text-sm tracking-[0.2em]">INITIALIZING AUREM...</p>
        </motion.div>
      </div>
    );
  }

  const agentIcons = {
    scout: Eye,
    architect: Brain,
    envoy: Radio,
    closer: Crosshair,
    system: Terminal
  };

  const agentColors = {
    scout: '#D4AF37',
    architect: '#009874',
    envoy: '#D4AF37',
    closer: '#009874',
    system: '#666'
  };

  const usagePercent = Math.min(100, ((user?.usage?.crew_executions || 0) / (user?.usage?.crew_limit || 500)) * 100);

  return (
    <div className="min-h-screen bg-[#050505] text-[#F4F4F4] flex" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Sidebar */}
      <motion.aside 
        initial={{ x: -20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        className="w-72 bg-[#0A0A0A] border-r border-[#151515] flex flex-col"
      >
        <div className="p-6 border-b border-[#151515]">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded bg-gradient-to-br from-[#D4AF37] to-[#8B7355] flex items-center justify-center">
                <Target className="w-5 h-5 text-[#050505]" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-[#009874] rounded-full animate-pulse"></div>
            </div>
            <div>
              <div className="text-sm tracking-[0.15em]" style={{ fontFamily: "'Playfair Display', serif" }}>POLARIS BUILT</div>
              <div className="text-xs text-[#D4AF37] tracking-widest">AUREM • {user?.tier?.toUpperCase()}</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4">
          <p className="text-[10px] text-[#333] tracking-[0.2em] uppercase mb-3 px-4">Operations</p>
          <div className="space-y-1">
            {[
              { id: 'command', icon: LayoutGrid, label: 'Command Center' },
              { id: 'vanguard', icon: Crosshair, label: 'Vanguard Swarm' },
              { id: 'livelog', icon: Terminal, label: 'Live Log', badge: liveLogs.length > 0 },
              { id: 'tools', icon: Settings, label: 'Integrations' },
              { id: 'ledger', icon: BarChart3, label: 'Performance Ledger' },
              { id: 'api', icon: Key, label: 'API Access' }
            ].map((item) => (
              <motion.button
                key={item.id}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-4 py-3 rounded text-sm transition-all ${
                  activeTab === item.id 
                    ? 'bg-[#D4AF37]/10 text-[#D4AF37] border-l-2 border-[#D4AF37]' 
                    : 'text-[#555] hover:bg-[#0F0F0F] hover:text-[#888]'
                }`}
              >
                <span className="flex items-center gap-3">
                  <item.icon className="w-4 h-4" />
                  <span className="tracking-wide">{item.label}</span>
                </span>
                {item.badge && (
                  <span className="w-2 h-2 bg-[#009874] rounded-full animate-pulse"></span>
                )}
              </motion.button>
            ))}
          </div>
          
          {/* System Section */}
          <p className="text-[10px] text-[#333] tracking-[0.2em] uppercase mb-3 px-4 mt-6">System</p>
          <div className="space-y-1">
            {[
              { id: 'bughistory', icon: Bug, label: 'Bug History' },
              { id: 'security', icon: Shield, label: 'Security' }
            ].map((item) => (
              <motion.button
                key={item.id}
                whileHover={{ x: 4 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-4 py-3 rounded text-sm transition-all ${
                  activeTab === item.id 
                    ? 'bg-[#D4AF37]/10 text-[#D4AF37] border-l-2 border-[#D4AF37]' 
                    : 'text-[#555] hover:bg-[#0F0F0F] hover:text-[#888]'
                }`}
              >
                <span className="flex items-center gap-3">
                  <item.icon className="w-4 h-4" />
                  <span className="tracking-wide">{item.label}</span>
                </span>
              </motion.button>
            ))}
          </div>
        </nav>

        {/* Usage Card */}
        <div className="p-4 border-t border-[#151515]">
          <div className="p-4 bg-[#0F0F0F] rounded-lg border border-[#151515]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-[#444] tracking-[0.15em] uppercase">Swarm Missions</span>
              <span className="text-xs text-[#D4AF37]">{Math.round(usagePercent)}%</span>
            </div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-2xl font-light" style={{ fontFamily: "'Playfair Display', serif" }}>
                {user?.usage?.crew_executions || 0}
              </span>
              <span className="text-xs text-[#333]">/ {user?.usage?.crew_limit || 500}</span>
            </div>
            <div className="h-1 bg-[#151515] rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${usagePercent}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
                className="h-full bg-gradient-to-r from-[#D4AF37] to-[#009874] rounded-full"
              />
            </div>
          </div>

          <button 
            onClick={logout}
            className="w-full flex items-center gap-2 px-4 py-3 mt-3 text-sm text-[#444] hover:text-[#666] transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span className="tracking-wide">Disconnect</span>
          </button>
        </div>
      </motion.aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto flex flex-col">
        {/* Admin Status Bar */}
        <AdminStatusBar onSyncComplete={fetchAllData} />
        
        <motion.header 
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="sticky top-0 z-10 bg-[#050505]/95 backdrop-blur-xl border-b border-[#151515] px-8 py-5"
        >
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl" style={{ fontFamily: "'Playfair Display', serif" }}>
                {activeTab === 'command' && 'Command Center'}
                {activeTab === 'vanguard' && 'Vanguard Swarm'}
                {activeTab === 'livelog' && 'Live Agent Log'}
                {activeTab === 'tools' && 'Integrations'}
                {activeTab === 'ledger' && 'Performance Ledger'}
                {activeTab === 'api' && 'API Access'}
                {activeTab === 'bughistory' && 'Bug History'}
                {activeTab === 'security' && 'Security Dashboard'}
              </h1>
              <p className="text-xs text-[#444] mt-1 tracking-wide">Operator: {user?.full_name}</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-[#009874]/10 border border-[#009874]/30 rounded">
                <div className="w-2 h-2 bg-[#009874] rounded-full animate-pulse"></div>
                <span className="text-xs text-[#009874] tracking-wide">AUREM Online</span>
              </div>
              <motion.button 
                whileHover={{ rotate: 180 }}
                transition={{ duration: 0.3 }}
                onClick={fetchAllData}
                className="p-2.5 bg-[#0F0F0F] border border-[#151515] rounded hover:border-[#D4AF37]/40"
              >
                <RefreshCw className="w-4 h-4 text-[#555]" />
              </motion.button>
            </div>
          </div>
        </motion.header>

        <div className="p-8 flex-1">
          <AnimatePresence mode="wait">
            {/* Command Center */}
            {activeTab === 'command' && (
              <motion.div
                key="command"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                {/* KPI Cards */}
                <div className="grid grid-cols-4 gap-4">
                  <KPICard title="Active Swarms" value={activeMissions.filter(m => m.status === 'running').length} icon={Activity} trend="+2" trendUp />
                  <KPICard title="Prospects Found" value={activeMissions.reduce((sum, m) => sum + (m.metrics?.prospects_found || 0), 0)} icon={Eye} />
                  <KPICard title="Meetings Booked" value={activeMissions.reduce((sum, m) => sum + (m.metrics?.meetings_booked || 0), 0)} icon={Target} trend="+5" trendUp />
                  <KPICard title="Est. Pipeline" value="$48K" icon={DollarSign} highlight />
                </div>

                {/* Vanguard Agents Status */}
                <div>
                  <h2 className="text-lg mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>Vanguard Agents</h2>
                  <div className="grid grid-cols-4 gap-4">
                    {Object.entries(vanguardAgents).map(([id, agent]) => {
                      const Icon = agentIcons[id] || Users;
                      const color = agentColors[id] || '#666';
                      return (
                        <motion.div
                          key={id}
                          whileHover={{ y: -4, borderColor: color }}
                          className="p-5 bg-[#0A0A0A] rounded-lg border border-[#151515] transition-all"
                        >
                          <div className="flex items-center justify-between mb-3">
                            <div 
                              className="w-10 h-10 rounded-lg flex items-center justify-center"
                              style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
                            >
                              <Icon className="w-5 h-5" style={{ color }} />
                            </div>
                            <span className="text-[10px] tracking-[0.15em]" style={{ color }}>{agent.role}</span>
                          </div>
                          <h3 className="font-medium mb-1">{agent.name}</h3>
                          <p className="text-xs text-[#444]">{agent.toolset}</p>
                          <div className="mt-3 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: color }}></div>
                            <span className="text-[10px] text-[#333]">Ready</span>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </div>

                {/* Recent Activity + Mini Live Log */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Recent Missions */}
                  <div className="bg-[#0A0A0A] border border-[#151515] rounded-lg overflow-hidden">
                    <div className="px-6 py-4 border-b border-[#151515] flex items-center justify-between">
                      <h3 className="text-sm font-medium" style={{ fontFamily: "'Playfair Display', serif" }}>Recent Missions</h3>
                      <span className="text-[10px] text-[#444] tracking-[0.15em] uppercase">Last 24H</span>
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                      {activeMissions.length === 0 ? (
                        <div className="p-8 text-center text-[#333] text-sm">
                          No active missions. Launch Vanguard to begin.
                        </div>
                      ) : (
                        activeMissions.map((mission) => (
                          <motion.div 
                            key={mission.mission_id}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="px-6 py-3 border-b border-[#151515]/50 hover:bg-[#0F0F0F] cursor-pointer"
                            onClick={() => setSelectedMission(mission.mission_id)}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-sm">{mission.industry_target}</p>
                                <p className="text-xs text-[#444]">{mission.mission_id?.slice(0, 16)}</p>
                              </div>
                              <StatusBadge status={mission.status} />
                            </div>
                          </motion.div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Mini Live Log */}
                  <div className="bg-[#0A0A0A] border border-[#151515] rounded-lg overflow-hidden">
                    <div className="px-6 py-4 border-b border-[#151515] flex items-center justify-between">
                      <h3 className="text-sm font-medium flex items-center gap-2" style={{ fontFamily: "'Playfair Display', serif" }}>
                        <Terminal className="w-4 h-4 text-[#D4AF37]" />
                        Live Agent Feed
                      </h3>
                      <div className="w-2 h-2 bg-[#009874] rounded-full animate-pulse"></div>
                    </div>
                    <div className="max-h-64 overflow-y-auto p-4 font-mono text-xs">
                      {liveLogs.length === 0 ? (
                        <p className="text-[#333]">Awaiting agent activity...</p>
                      ) : (
                        liveLogs.slice(-8).map((log, i) => (
                          <LogEntry key={i} log={log} agentIcons={agentIcons} agentColors={agentColors} />
                        ))
                      )}
                      <div ref={logsEndRef} />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Vanguard Swarm Tab */}
            {activeTab === 'vanguard' && (
              <motion.div
                key="vanguard"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-8"
              >
                <div className="text-center mb-8">
                  <h2 className="text-2xl mb-2" style={{ fontFamily: "'Playfair Display', serif" }}>Launch Vanguard Mission</h2>
                  <p className="text-[#555] text-sm">Select target industry to deploy the swarm</p>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { id: 'tech_startups', name: 'Tech Startups', icon: Zap, desc: 'Series A funding, new hires' },
                    { id: 'ecommerce', name: 'E-Commerce', icon: Globe, desc: 'Holiday prep, expansion' },
                    { id: 'saas', name: 'SaaS Companies', icon: BarChart3, desc: 'MRR milestones, launches' },
                    { id: 'agencies', name: 'Agencies', icon: Users, desc: 'Client wins, hiring' }
                  ].map((target) => (
                    <motion.button
                      key={target.id}
                      whileHover={{ y: -4, borderColor: '#D4AF37' }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => launchVanguard(target.id)}
                      disabled={executing === target.id}
                      className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515] text-left transition-all group disabled:opacity-50"
                    >
                      <div className="w-12 h-12 rounded-lg bg-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center justify-center mb-4 group-hover:bg-[#D4AF37]/20">
                        <target.icon className="w-5 h-5 text-[#D4AF37]" />
                      </div>
                      <h3 className="font-medium mb-1 group-hover:text-[#D4AF37] transition-colors">{target.name}</h3>
                      <p className="text-xs text-[#444]">{target.desc}</p>
                      <div className="mt-4 pt-4 border-t border-[#151515]">
                        {executing === target.id ? (
                          <span className="text-xs text-[#D4AF37] flex items-center gap-2">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Deploying...
                          </span>
                        ) : (
                          <span className="text-xs text-[#555] group-hover:text-[#D4AF37]">Click to deploy →</span>
                        )}
                      </div>
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Live Log Tab */}
            {activeTab === 'livelog' && (
              <motion.div
                key="livelog"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <div className="bg-[#0A0A0A] border border-[#151515] rounded-lg overflow-hidden">
                  <div className="px-6 py-4 border-b border-[#151515] flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Terminal className="w-5 h-5 text-[#D4AF37]" />
                      <h3 className="font-medium" style={{ fontFamily: "'Playfair Display', serif" }}>Agent Activity Stream</h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-[#009874] rounded-full animate-pulse"></div>
                      <span className="text-xs text-[#009874]">Live</span>
                    </div>
                  </div>
                  <div className="h-[500px] overflow-y-auto p-6 font-mono text-sm bg-[#050505]">
                    {liveLogs.length === 0 ? (
                      <div className="text-center text-[#333] py-20">
                        <Terminal className="w-12 h-12 mx-auto mb-4 opacity-30" />
                        <p>Awaiting agent activity...</p>
                        <p className="text-xs mt-2">Launch a Vanguard mission to see live logs</p>
                      </div>
                    ) : (
                      liveLogs.map((log, i) => (
                        <LogEntry key={i} log={log} agentIcons={agentIcons} agentColors={agentColors} expanded />
                      ))
                    )}
                    <div ref={logsEndRef} />
                  </div>
                </div>
              </motion.div>
            )}

            {/* Other tabs remain similar but with AUREM branding */}
            {activeTab === 'tools' && (
              <motion.div
                key="tools"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="grid grid-cols-2 lg:grid-cols-3 gap-4"
              >
                {user?.tools_available?.map((tool) => {
                  const status = toolsStatus[tool];
                  const icons = { email: Mail, whatsapp: MessageSquare, voice: Phone, chatbot: Globe, browser_agent: Eye, tts: Zap };
                  const ToolIcon = icons[tool] || Settings;
                  
                  return (
                    <motion.div 
                      key={tool} 
                      whileHover={{ borderColor: status?.connected ? '#009874' : '#D4AF37' }}
                      className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515] transition-all"
                    >
                      <div className="flex items-center gap-4 mb-4">
                        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                          status?.connected ? 'bg-[#009874]/10 border border-[#009874]/30' : 'bg-[#151515]'
                        }`}>
                          <ToolIcon className={`w-5 h-5 ${status?.connected ? 'text-[#009874]' : 'text-[#444]'}`} />
                        </div>
                        <div>
                          <h3 className="font-medium capitalize">{tool.replace('_', ' ')}</h3>
                          <p className="text-xs text-[#444]">{status?.connected ? 'Connected' : 'Not configured'}</p>
                        </div>
                      </div>
                      <button className={`w-full py-2.5 rounded text-sm tracking-wide transition-all ${
                        status?.connected 
                          ? 'bg-[#151515] text-[#555] hover:bg-[#1A1A1A]' 
                          : 'bg-[#D4AF37]/10 text-[#D4AF37] border border-[#D4AF37]/30 hover:bg-[#D4AF37]/20'
                      }`}>
                        {status?.connected ? 'Manage' : 'Configure'}
                      </button>
                    </motion.div>
                  );
                })}
              </motion.div>
            )}

            {activeTab === 'api' && (
              <motion.div
                key="api"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-2xl space-y-6"
              >
                <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                  <h3 className="text-sm font-medium mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>AUREM API Credentials</h3>
                  <div className="p-4 bg-[#050505] rounded border border-[#151515] font-mono text-sm text-[#D4AF37] mb-4">
                    {user?.api_key || 'Loading...'}
                  </div>
                  <p className="text-xs text-[#444]">
                    Header: <code className="bg-[#151515] px-2 py-1 rounded text-[#D4AF37]">X-API-Key</code>
                  </p>
                </div>

                <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                  <h3 className="text-sm font-medium mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>Launch Vanguard via API</h3>
                  <pre className="p-4 bg-[#050505] rounded border border-[#151515] text-xs overflow-x-auto text-[#666]">
{`curl -X POST ${API_URL}/api/aurem/mission/create \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"industry_target": "tech_startups"}'`}
                  </pre>
                </div>
              </motion.div>
            )}

            {/* Bug History Tab */}
            {activeTab === 'bughistory' && (
              <motion.div
                key="bughistory"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
              >
                <AuremBugHistory />
              </motion.div>
            )}

            {/* Security Dashboard Tab */}
            {activeTab === 'security' && (
              <motion.div
                key="security"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-6"
              >
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                    <div className="flex items-center gap-3 mb-4">
                      <Shield className="w-5 h-5 text-[#009874]" />
                      <h3 className="font-medium">Encryption</h3>
                    </div>
                    <p className="text-xs text-[#444] mb-4">AES-256 Fernet encryption for sensitive prospect data</p>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-[#009874]" />
                      <span className="text-xs text-[#009874]">Active</span>
                    </div>
                  </div>
                  
                  <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                    <div className="flex items-center gap-3 mb-4">
                      <Key className="w-5 h-5 text-[#D4AF37]" />
                      <h3 className="font-medium">JWT Auth</h3>
                    </div>
                    <p className="text-xs text-[#444] mb-4">2-hour expiry, tier-based access control</p>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-[#009874]" />
                      <span className="text-xs text-[#009874]">Active</span>
                    </div>
                  </div>
                  
                  <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                    <div className="flex items-center gap-3 mb-4">
                      <AlertCircle className="w-5 h-5 text-[#D4AF37]" />
                      <h3 className="font-medium">Rate Limiting</h3>
                    </div>
                    <p className="text-xs text-[#444] mb-4">20 req/hr unauth, 200 req/hr auth</p>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-[#009874]" />
                      <span className="text-xs text-[#009874]">Active</span>
                    </div>
                  </div>
                </div>
                
                <div className="p-6 bg-[#0A0A0A] rounded-lg border border-[#151515]">
                  <h3 className="font-medium mb-4" style={{ fontFamily: "'Playfair Display', serif" }}>Security Features</h3>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { name: 'Row-Level Security', desc: 'Users only see their own data' },
                      { name: 'Path Blocking', desc: '/.env, /wp-admin, /.git blocked' },
                      { name: 'Base64 Prompts', desc: 'Agent prompts hidden from code' },
                      { name: 'Suspicious Detection', desc: '10+ identical requests = 24h block' },
                    ].map((feature, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-[#050505] rounded">
                        <CheckCircle className="w-4 h-4 text-[#009874] mt-0.5" />
                        <div>
                          <p className="text-sm">{feature.name}</p>
                          <p className="text-xs text-[#444]">{feature.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
};

// KPI Card Component
const KPICard = ({ title, value, icon: Icon, trend, trendUp, highlight }) => (
  <motion.div 
    whileHover={{ y: -2, borderColor: highlight ? '#D4AF37' : '#222' }}
    className={`p-5 rounded-lg border transition-all ${
      highlight 
        ? 'bg-gradient-to-br from-[#D4AF37]/10 to-[#0A0A0A] border-[#D4AF37]/30' 
        : 'bg-[#0A0A0A] border-[#151515]'
    }`}
  >
    <div className="flex items-center justify-between mb-3">
      <span className="text-[10px] text-[#444] tracking-[0.15em] uppercase">{title}</span>
      <Icon className={`w-4 h-4 ${highlight ? 'text-[#D4AF37]' : 'text-[#333]'}`} />
    </div>
    <div className="flex items-end justify-between">
      <span className="text-2xl font-light" style={{ fontFamily: "'Playfair Display', serif" }}>{value}</span>
      {trend && (
        <span className={`text-xs ${trendUp ? 'text-[#009874]' : 'text-red-400'}`}>{trend}</span>
      )}
    </div>
  </motion.div>
);

// Log Entry Component
const LogEntry = ({ log, agentIcons, agentColors, expanded }) => {
  const Icon = agentIcons[log.agent] || Terminal;
  const color = agentColors[log.agent] || '#666';
  
  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-start gap-3 ${expanded ? 'py-3 border-b border-[#151515]/50' : 'py-1.5'}`}
    >
      <div 
        className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0 mt-0.5"
        style={{ backgroundColor: `${color}20` }}
      >
        <Icon className="w-3 h-3" style={{ color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[10px] tracking-wider uppercase" style={{ color }}>{log.agent}</span>
          <span className="text-[10px] text-[#333]">{new Date(log.timestamp).toLocaleTimeString()}</span>
        </div>
        <p className="text-[#888] break-words">{log.message}</p>
        {expanded && log.data && Object.keys(log.data).length > 0 && (
          <div className="mt-2 p-2 bg-[#0A0A0A] rounded text-[10px] text-[#555]">
            {JSON.stringify(log.data, null, 2)}
          </div>
        )}
      </div>
    </motion.div>
  );
};

// Status Badge Component
const StatusBadge = ({ status }) => {
  const styles = {
    completed: 'bg-[#009874]/10 text-[#009874] border-[#009874]/30',
    running: 'bg-[#D4AF37]/10 text-[#D4AF37] border-[#D4AF37]/30',
    initializing: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
    failed: 'bg-red-500/10 text-red-400 border-red-500/30'
  };

  return (
    <span className={`px-2 py-1 rounded border text-[10px] tracking-wider uppercase ${styles[status] || 'bg-[#151515] text-[#444]'}`}>
      {status}
    </span>
  );
};

export default PlatformDashboard;
