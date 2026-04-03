/**
 * ReRoots AI Orchestrator Command Center
 * The Master Brain interface for controlling all AI agents
 */

import React, { useState, useEffect, useRef } from 'react';
import { 
  Brain, Send, Zap, Play, Pause, RefreshCw, 
  CheckCircle, XCircle, Clock, Activity, 
  ChevronRight, Settings, Terminal, Workflow,
  Mic, Globe, Users, RotateCcw, Router, Volume2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const OrchestratorCommandCenter = () => {
  const [activeTab, setActiveTab] = useState('command');
  const [command, setCommand] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [agents, setAgents] = useState({});
  const [workflows, setWorkflows] = useState({});
  const [health, setHealth] = useState(null);
  const [executions, setExecutions] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  // Tech Stack state
  const [llmModels, setLlmModels] = useState({});
  const [browserCapabilities, setBrowserCapabilities] = useState({});
  const [voiceConfig, setVoiceConfig] = useState({});
  const [crewTemplates, setCrewTemplates] = useState({});
  const [oodaCycles, setOodaCycles] = useState({});
  const wsRef = useRef(null);
  const chatEndRef = useRef(null);

  // Initialize
  useEffect(() => {
    fetchAgents();
    fetchWorkflows();
    fetchHealth();
    fetchExecutions();
    fetchTechStack();
    connectWebSocket();

    const healthInterval = setInterval(fetchHealth, 30000);
    return () => {
      clearInterval(healthInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Fetch Tech Stack APIs
  const fetchTechStack = async () => {
    try {
      const [llmRes, browserRes, voiceRes, crewRes, oodaRes] = await Promise.all([
        fetch(`${API_URL}/api/llm-router/models`),
        fetch(`${API_URL}/api/browser-agent/capabilities`),
        fetch(`${API_URL}/api/voice/voices`),
        fetch(`${API_URL}/api/crews/templates`),
        fetch(`${API_URL}/api/ooda/cycles`)
      ]);
      
      if (llmRes.ok) setLlmModels(await llmRes.json());
      if (browserRes.ok) setBrowserCapabilities(await browserRes.json());
      if (voiceRes.ok) setVoiceConfig(await voiceRes.json());
      if (crewRes.ok) setCrewTemplates(await crewRes.json());
      if (oodaRes.ok) setOodaCycles(await oodaRes.json());
    } catch (err) {
      console.error('Failed to fetch tech stack:', err);
    }
  };

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const connectWebSocket = () => {
    const wsUrl = API_URL.replace('https://', 'wss://').replace('http://', 'ws://');
    const ws = new WebSocket(`${wsUrl}/api/orchestrator/ws`);

    ws.onopen = () => {
      setWsConnected(true);
      addSystemMessage('Connected to Orchestrator Brain');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleWsMessage(data);
    };

    ws.onclose = () => {
      setWsConnected(false);
      addSystemMessage('Disconnected from Orchestrator. Reconnecting...');
      setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    wsRef.current = ws;
  };

  const handleWsMessage = (data) => {
    if (data.type === 'task_update') {
      addSystemMessage(`🤖 ${data.agent}: ${data.status} - ${data.action || ''}`);
      fetchExecutions();
    } else if (data.type === 'workflow_update') {
      addSystemMessage(`📋 Workflow ${data.workflow}: ${data.status}`);
      fetchExecutions();
    }
  };

  const addSystemMessage = (text) => {
    setChatHistory(prev => [...prev, {
      type: 'system',
      text,
      timestamp: new Date()
    }]);
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch(`${API_URL}/api/orchestrator/agents`);
      if (res.ok) {
        const data = await res.json();
        setAgents(data.agents || {});
      }
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    }
  };

  const fetchWorkflows = async () => {
    try {
      const res = await fetch(`${API_URL}/api/orchestrator/workflows`);
      if (res.ok) {
        const data = await res.json();
        setWorkflows(data.workflows || {});
      }
    } catch (err) {
      console.error('Failed to fetch workflows:', err);
    }
  };

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_URL}/api/orchestrator/health`);
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch (err) {
      console.error('Failed to fetch health:', err);
    }
  };

  const fetchExecutions = async () => {
    try {
      const res = await fetch(`${API_URL}/api/orchestrator/executions?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setExecutions([
          ...(data.orchestrator_executions || []),
          ...(data.workflow_executions || [])
        ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 10));
      }
    } catch (err) {
      console.error('Failed to fetch executions:', err);
    }
  };

  const sendCommand = async () => {
    if (!command.trim() || isProcessing) return;

    const userMessage = {
      type: 'user',
      text: command,
      timestamp: new Date()
    };

    setChatHistory(prev => [...prev, userMessage]);
    setCommand('');
    setIsProcessing(true);

    try {
      const res = await fetch(`${API_URL}/api/orchestrator/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: command,
          priority: 'normal',
          async_execution: true
        })
      });

      const data = await res.json();

      const aiMessage = {
        type: 'ai',
        text: data.plan?.understood_intent || 'Processing your command...',
        plan: data.plan,
        execution_id: data.execution_id,
        status: data.status,
        timestamp: new Date()
      };

      setChatHistory(prev => [...prev, aiMessage]);
      fetchExecutions();

    } catch (err) {
      setChatHistory(prev => [...prev, {
        type: 'error',
        text: 'Failed to process command. Please try again.',
        timestamp: new Date()
      }]);
    }

    setIsProcessing(false);
  };

  const executeWorkflow = async (workflowId) => {
    try {
      const res = await fetch(`${API_URL}/api/orchestrator/workflow/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workflow_id: workflowId,
          priority: 'normal'
        })
      });

      const data = await res.json();
      addSystemMessage(`🚀 Started workflow: ${workflowId} (${data.execution_id})`);
      fetchExecutions();
    } catch (err) {
      addSystemMessage(`❌ Failed to start workflow: ${workflowId}`);
    }
  };

  // Example commands
  const exampleCommands = [
    "Analyze customer sentiment from recent reviews",
    "Find at-risk customers and send them a retention email",
    "Check inventory levels and alert me about low stock",
    "Generate product descriptions for all new products",
    "Translate the homepage to Spanish and French",
    "Create a video demo for the bestselling serum"
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-800 to-gray-900 text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/30 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                <Brain className="w-7 h-7" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Orchestrator Command Center</h1>
                <p className="text-xs text-gray-400">ReRoots AI Master Brain</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Connection Status */}
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                wsConnected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
                {wsConnected ? 'Live' : 'Offline'}
              </div>

              {/* Health Score */}
              {health && (
                <div className={`px-3 py-1.5 rounded-full text-sm ${
                  health.overall_health_score >= 80 ? 'bg-green-500/20 text-green-400' :
                  health.overall_health_score >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-red-500/20 text-red-400'
                }`}>
                  Health: {health.overall_health_score}%
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="border-b border-white/10 bg-black/20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex gap-1">
            {[
              { id: 'command', label: 'Command Center', icon: Terminal },
              { id: 'agents', label: 'AI Agents', icon: Brain },
              { id: 'workflows', label: 'Workflows', icon: Workflow },
              { id: 'techstack', label: 'Tech Stack', icon: Router },
              { id: 'monitor', label: 'Monitor', icon: Activity }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-5 py-3 font-medium transition-colors relative ${
                  activeTab === tab.id ? 'text-purple-400' : 'text-gray-400 hover:text-white'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
                {activeTab === tab.id && (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-400" />
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'command' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Chat Interface */}
            <div className="lg:col-span-2 flex flex-col h-[calc(100vh-220px)] bg-white/5 rounded-2xl border border-white/10 overflow-hidden">
              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {chatHistory.length === 0 && (
                  <div className="text-center py-12">
                    <Brain className="w-16 h-16 mx-auto text-purple-400 mb-4" />
                    <h3 className="text-lg font-semibold mb-2">Welcome to Command Center</h3>
                    <p className="text-gray-400 text-sm mb-6">
                      Give me natural language commands and I'll orchestrate your AI agents.
                    </p>
                    <div className="space-y-2">
                      <p className="text-xs text-gray-500">Try these commands:</p>
                      {exampleCommands.slice(0, 3).map((cmd, i) => (
                        <button
                          key={i}
                          onClick={() => setCommand(cmd)}
                          className="block w-full text-left px-4 py-2 bg-white/5 rounded-lg text-sm text-gray-300 hover:bg-white/10 transition-colors"
                        >
                          "{cmd}"
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {chatHistory.map((msg, idx) => (
                  <ChatMessage key={idx} message={msg} />
                ))}

                {isProcessing && (
                  <div className="flex items-center gap-3 p-4 bg-purple-500/10 rounded-xl border border-purple-500/20">
                    <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
                      <Brain className="w-5 h-5 text-purple-400 animate-pulse" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-purple-400">Orchestrator</span>
                        <span className="text-xs text-gray-500">analyzing...</span>
                      </div>
                      <div className="flex gap-1 mt-2">
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div className="p-4 border-t border-white/10 bg-black/20">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={command}
                    onChange={(e) => setCommand(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendCommand()}
                    placeholder="Tell me what you want to do..."
                    className="flex-1 px-4 py-3 bg-white/10 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:border-purple-500 focus:outline-none"
                    disabled={isProcessing}
                  />
                  <button
                    onClick={sendCommand}
                    disabled={isProcessing || !command.trim()}
                    className="px-6 py-3 bg-gradient-to-r from-purple-500 to-blue-600 rounded-xl font-medium flex items-center gap-2 hover:from-purple-400 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    <Send className="w-5 h-5" />
                    Execute
                  </button>
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {/* Quick Actions */}
              <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Zap className="w-4 h-4 text-yellow-400" />
                  Quick Workflows
                </h3>
                <div className="space-y-2">
                  {Object.entries(workflows).slice(0, 4).map(([id, wf]) => (
                    <button
                      key={id}
                      onClick={() => executeWorkflow(id)}
                      className="w-full text-left px-3 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition-colors group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">{wf.name}</span>
                        <Play className="w-4 h-4 text-gray-500 group-hover:text-purple-400" />
                      </div>
                      <p className="text-xs text-gray-500 mt-1">{wf.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Recent Executions */}
              <div className="p-4 bg-white/5 rounded-xl border border-white/10">
                <h3 className="font-semibold mb-3 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-blue-400" />
                  Recent Executions
                </h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {executions.slice(0, 5).map((exec, i) => (
                    <div key={i} className="px-3 py-2 bg-white/5 rounded-lg">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono text-gray-400">
                          {exec.execution_id?.slice(0, 12)}...
                        </span>
                        <StatusBadge status={exec.status} />
                      </div>
                      <p className="text-xs text-gray-500 mt-1 truncate">
                        {exec.command || exec.workflow_id}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <AgentsView agents={agents} health={health} />
        )}

        {activeTab === 'workflows' && (
          <WorkflowsView workflows={workflows} onExecute={executeWorkflow} />
        )}

        {activeTab === 'monitor' && (
          <MonitorView health={health} executions={executions} onRefresh={fetchHealth} />
        )}

        {activeTab === 'techstack' && (
          <TechStackView 
            llmModels={llmModels}
            browserCapabilities={browserCapabilities}
            voiceConfig={voiceConfig}
            crewTemplates={crewTemplates}
            oodaCycles={oodaCycles}
            onRefresh={fetchTechStack}
          />
        )}
      </main>
    </div>
  );
};


// Chat Message Component
const ChatMessage = ({ message }) => {
  if (message.type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-4 py-3 bg-purple-500/20 rounded-xl rounded-br-sm border border-purple-500/30">
          <p className="text-sm">{message.text}</p>
          <p className="text-xs text-gray-500 mt-1">
            {new Date(message.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </div>
    );
  }

  if (message.type === 'ai') {
    return (
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center flex-shrink-0">
          <Brain className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-purple-400">Orchestrator</span>
            <StatusBadge status={message.status} />
          </div>
          <div className="p-4 bg-white/5 rounded-xl border border-white/10">
            <p className="text-sm mb-3">{message.text}</p>
            
            {message.plan?.execution_plan && (
              <div className="mt-3 pt-3 border-t border-white/10">
                <p className="text-xs text-gray-500 mb-2">Execution Plan:</p>
                <div className="space-y-1">
                  {message.plan.execution_plan.map((step, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <div className="w-5 h-5 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
                        {step.step}
                      </div>
                      <span className="text-gray-400">{step.agent}</span>
                      <ChevronRight className="w-3 h-3 text-gray-600" />
                      <span>{step.action}</span>
                    </div>
                  ))}
                </div>
                {message.plan.estimated_time && (
                  <p className="text-xs text-gray-500 mt-2">
                    ⏱️ Estimated: {message.plan.estimated_time}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (message.type === 'system') {
    return (
      <div className="text-center">
        <span className="text-xs text-gray-500 bg-white/5 px-3 py-1 rounded-full">
          {message.text}
        </span>
      </div>
    );
  }

  if (message.type === 'error') {
    return (
      <div className="flex gap-3">
        <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center flex-shrink-0">
          <XCircle className="w-5 h-5 text-red-400" />
        </div>
        <div className="p-4 bg-red-500/10 rounded-xl border border-red-500/30">
          <p className="text-sm text-red-400">{message.text}</p>
        </div>
      </div>
    );
  }

  return null;
};


// Status Badge Component
const StatusBadge = ({ status }) => {
  const styles = {
    completed: 'bg-green-500/20 text-green-400',
    running: 'bg-blue-500/20 text-blue-400',
    executing: 'bg-blue-500/20 text-blue-400',
    pending: 'bg-yellow-500/20 text-yellow-400',
    failed: 'bg-red-500/20 text-red-400',
    planned: 'bg-purple-500/20 text-purple-400'
  };

  const icons = {
    completed: CheckCircle,
    running: RefreshCw,
    executing: RefreshCw,
    pending: Clock,
    failed: XCircle,
    planned: Brain
  };

  const Icon = icons[status] || Clock;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${styles[status] || 'bg-gray-500/20 text-gray-400'}`}>
      <Icon className={`w-3 h-3 ${status === 'running' || status === 'executing' ? 'animate-spin' : ''}`} />
      {status}
    </span>
  );
};


// Agents View
const AgentsView = ({ agents, health }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Object.entries(agents).map(([id, agent]) => {
        const agentHealth = health?.agent_health?.[id] || {};
        
        return (
          <div key={id} className="p-4 bg-white/5 rounded-xl border border-white/10 hover:border-purple-500/50 transition-all">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  agentHealth.status === 'healthy' ? 'bg-green-500/20' :
                  agentHealth.status === 'degraded' ? 'bg-yellow-500/20' :
                  'bg-red-500/20'
                }`}>
                  <Brain className={`w-5 h-5 ${
                    agentHealth.status === 'healthy' ? 'text-green-400' :
                    agentHealth.status === 'degraded' ? 'text-yellow-400' :
                    'text-red-400'
                  }`} />
                </div>
                <div>
                  <div className="font-medium text-sm">{agent.name}</div>
                  <div className="text-xs text-gray-500">{id}</div>
                </div>
              </div>
              <StatusBadge status={agentHealth.status || 'healthy'} />
            </div>

            <div className="space-y-2 mb-3">
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Success Rate</span>
                <span className={agentHealth.success_rate >= 90 ? 'text-green-400' : 'text-yellow-400'}>
                  {agentHealth.success_rate || 100}%
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Tasks (1h)</span>
                <span>{agentHealth.tasks_last_hour || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Avg Response</span>
                <span>{agent.avg_response_time}s</span>
              </div>
            </div>

            <div className="pt-3 border-t border-white/10">
              <p className="text-xs text-gray-500 mb-2">Capabilities:</p>
              <div className="flex flex-wrap gap-1">
                {agent.capabilities.slice(0, 3).map((cap, i) => (
                  <span key={i} className="px-2 py-0.5 bg-purple-500/20 rounded text-xs text-purple-400">
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};


// Workflows View
const WorkflowsView = ({ workflows, onExecute }) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Workflow Templates</h2>
        <button className="px-4 py-2 bg-purple-500/20 text-purple-400 rounded-lg text-sm hover:bg-purple-500/30">
          + Create Custom Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(workflows).map(([id, wf]) => (
          <div key={id} className="p-5 bg-white/5 rounded-xl border border-white/10 hover:border-purple-500/50 transition-all">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">{wf.name}</h3>
              <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded">
                {wf.trigger}
              </span>
            </div>

            <p className="text-sm text-gray-400 mb-4">{wf.description}</p>

            <div className="space-y-2 mb-4">
              {wf.steps.map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <div className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                    {i + 1}
                  </div>
                  <span className="text-purple-400">{step.agent}</span>
                  <ChevronRight className="w-3 h-3 text-gray-600" />
                  <span className="text-gray-400">{step.action}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => onExecute(id)}
              className="w-full py-2 bg-gradient-to-r from-purple-500 to-blue-600 rounded-lg font-medium text-sm flex items-center justify-center gap-2 hover:from-purple-400 hover:to-blue-500 transition-all"
            >
              <Play className="w-4 h-4" />
              Execute Workflow
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};


// Monitor View
const MonitorView = ({ health, executions, onRefresh }) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">System Monitor</h2>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-white/10 rounded-lg text-sm flex items-center gap-2 hover:bg-white/20"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {health && (
        <>
          {/* Health Overview */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className={`p-5 rounded-xl border ${
              health.overall_health_score >= 80 ? 'bg-green-500/10 border-green-500/30' :
              health.overall_health_score >= 50 ? 'bg-yellow-500/10 border-yellow-500/30' :
              'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-sm text-gray-400 mb-1">Overall Health</div>
              <div className="text-3xl font-bold">{health.overall_health_score}%</div>
              <div className={`text-sm mt-1 ${
                health.orchestrator_status === 'healthy' ? 'text-green-400' : 'text-yellow-400'
              }`}>
                {health.orchestrator_status}
              </div>
            </div>

            <div className="p-5 bg-white/5 rounded-xl border border-white/10">
              <div className="text-sm text-gray-400 mb-1">Commands (1h)</div>
              <div className="text-3xl font-bold">{health.executions_last_hour?.commands || 0}</div>
              <div className="text-sm text-gray-500 mt-1">
                {health.executions_last_hour?.failures || 0} failed
              </div>
            </div>

            <div className="p-5 bg-white/5 rounded-xl border border-white/10">
              <div className="text-sm text-gray-400 mb-1">Workflows (1h)</div>
              <div className="text-3xl font-bold">{health.executions_last_hour?.workflows || 0}</div>
            </div>

            <div className="p-5 bg-white/5 rounded-xl border border-white/10">
              <div className="text-sm text-gray-400 mb-1">Live Connections</div>
              <div className="text-3xl font-bold">{health.active_websocket_connections || 0}</div>
            </div>
          </div>

          {/* Agent Status */}
          <div className="p-5 bg-white/5 rounded-xl border border-white/10">
            <h3 className="font-semibold mb-4">Agent Status</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {Object.entries(health.agent_health || {}).map(([id, agent]) => (
                <div key={id} className={`p-3 rounded-lg ${
                  agent.status === 'healthy' ? 'bg-green-500/10' :
                  agent.status === 'degraded' ? 'bg-yellow-500/10' :
                  'bg-red-500/10'
                }`}>
                  <div className="text-xs font-medium truncate">{id}</div>
                  <div className="text-lg font-bold">{agent.success_rate}%</div>
                  <div className="text-xs text-gray-500">{agent.tasks_last_hour} tasks</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Recent Executions */}
      <div className="p-5 bg-white/5 rounded-xl border border-white/10">
        <h3 className="font-semibold mb-4">Recent Executions</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-white/10">
                <th className="pb-3">ID</th>
                <th className="pb-3">Type</th>
                <th className="pb-3">Command/Workflow</th>
                <th className="pb-3">Status</th>
                <th className="pb-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((exec, i) => (
                <tr key={i} className="border-b border-white/5">
                  <td className="py-3 text-xs font-mono text-gray-400">
                    {exec.execution_id?.slice(0, 16)}...
                  </td>
                  <td className="py-3">
                    <span className="text-xs px-2 py-0.5 bg-white/10 rounded">
                      {exec.workflow_id ? 'workflow' : 'command'}
                    </span>
                  </td>
                  <td className="py-3 text-sm max-w-xs truncate">
                    {exec.command || exec.workflow_id}
                  </td>
                  <td className="py-3">
                    <StatusBadge status={exec.status} />
                  </td>
                  <td className="py-3 text-xs text-gray-500">
                    {new Date(exec.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};


// Tech Stack View - OpenRouter, Browser Agent, Voice, CrewAI, OODA
const TechStackView = ({ llmModels, browserCapabilities, voiceConfig, crewTemplates, oodaCycles, onRefresh }) => {
  const [selectedLLM, setSelectedLLM] = useState('gpt-5.2');
  const [llmStrategy, setLlmStrategy] = useState('balanced');
  const [ttsText, setTtsText] = useState('');
  const [selectedVoice, setSelectedVoice] = useState('brand_aura');
  const [crewLoading, setCrewLoading] = useState(null);
  const [oodaLoading, setOodaLoading] = useState(null);

  const API_URL = process.env.REACT_APP_BACKEND_URL || '';

  const executeCrew = async (crewId) => {
    setCrewLoading(crewId);
    try {
      const res = await fetch(`${API_URL}/api/crews/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ crew_id: crewId })
      });
      const data = await res.json();
      alert(`Crew started: ${data.execution_id}`);
    } catch (err) {
      alert('Failed to start crew');
    }
    setCrewLoading(null);
  };

  const executeOODA = async (cycleId) => {
    setOodaLoading(cycleId);
    try {
      const res = await fetch(`${API_URL}/api/ooda/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cycle_id: cycleId })
      });
      const data = await res.json();
      alert(`OODA cycle started: ${data.execution_id}`);
    } catch (err) {
      alert('Failed to start OODA cycle');
    }
    setOodaLoading(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Tech Stack Control Panel</h2>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-white/10 rounded-lg text-sm flex items-center gap-2 hover:bg-white/20"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LLM Router Panel */}
        <div className="p-5 bg-white/5 rounded-xl border border-white/10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
              <Router className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold">LLM Router</h3>
              <p className="text-xs text-gray-500">OpenRouter-style unified model access</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Available Models ({Object.keys(llmModels.models || {}).length})</label>
              <select
                value={selectedLLM}
                onChange={(e) => setSelectedLLM(e.target.value)}
                className="w-full px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-sm"
              >
                {Object.entries(llmModels.models || {}).map(([id, model]) => (
                  <option key={id} value={id} className="bg-gray-800">
                    {model.name} - ${model.cost_per_1k_output}/1K out
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Routing Strategy</label>
              <div className="flex flex-wrap gap-2">
                {Object.keys(llmModels.strategies || {}).map((strategy) => (
                  <button
                    key={strategy}
                    onClick={() => setLlmStrategy(strategy)}
                    className={`px-3 py-1 rounded-lg text-xs ${
                      llmStrategy === strategy 
                        ? 'bg-blue-500 text-white' 
                        : 'bg-white/10 text-gray-400 hover:bg-white/20'
                    }`}
                  >
                    {strategy}
                  </button>
                ))}
              </div>
            </div>

            <div className="pt-3 border-t border-white/10">
              <p className="text-xs text-gray-500 mb-2">Fallback Chains:</p>
              <div className="flex flex-wrap gap-2">
                {Object.keys(llmModels.fallback_chains || {}).map((chain) => (
                  <span key={chain} className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-xs">
                    {chain}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Voice Layer Panel */}
        <div className="p-5 bg-white/5 rounded-xl border border-white/10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Volume2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold">Voice Layer</h3>
              <p className="text-xs text-gray-500">Voxtral-style TTS with brand voice</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Voice ({Object.keys(voiceConfig.voices || {}).length} available)</label>
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="w-full px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-sm"
              >
                {Object.entries(voiceConfig.voices || {}).map(([id, voice]) => (
                  <option key={id} value={id} className="bg-gray-800">
                    {voice.name} ({voice.style})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-400 block mb-1">Text to Speech</label>
              <textarea
                value={ttsText}
                onChange={(e) => setTtsText(e.target.value)}
                placeholder="Enter text to convert to speech..."
                className="w-full px-3 py-2 bg-white/10 border border-white/10 rounded-lg text-sm h-20 resize-none"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <p className="text-xs text-gray-500 w-full mb-1">Languages: {Object.keys(voiceConfig.languages || {}).length}</p>
              {Object.entries(voiceConfig.languages || {}).slice(0, 6).map(([code, name]) => (
                <span key={code} className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">
                  {name}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Browser Agent Panel */}
        <div className="p-5 bg-white/5 rounded-xl border border-white/10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold">Browser Agent</h3>
              <p className="text-xs text-gray-500">PinchTab-style AI automation</p>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-xs text-gray-500">Available Actions ({Object.keys(browserCapabilities.actions || {}).length})</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(browserCapabilities.actions || {}).map(([action, desc]) => (
                <span key={action} className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">
                  {action}
                </span>
              ))}
            </div>

            <p className="text-xs text-gray-500 mt-4">Predefined Tasks</p>
            <div className="space-y-2">
              {Object.entries(browserCapabilities.predefined_tasks || {}).map(([id, task]) => (
                <div key={id} className="p-2 bg-white/5 rounded-lg flex justify-between items-center">
                  <div>
                    <p className="text-sm font-medium">{task.name}</p>
                    <p className="text-xs text-gray-500">{task.description}</p>
                  </div>
                  <button className="px-3 py-1 bg-green-500/20 text-green-400 rounded text-xs hover:bg-green-500/30">
                    Run
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CrewAI Panel */}
        <div className="p-5 bg-white/5 rounded-xl border border-white/10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold">CrewAI Swarms</h3>
              <p className="text-xs text-gray-500">Multi-agent crews for complex tasks</p>
            </div>
          </div>

          <div className="space-y-3">
            {Object.entries(crewTemplates.templates || {}).map(([id, crew]) => (
              <div key={id} className="p-3 bg-white/5 rounded-lg">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <p className="text-sm font-medium">{crew.name}</p>
                    <p className="text-xs text-gray-500">{crew.description}</p>
                  </div>
                  <button 
                    onClick={() => executeCrew(id)}
                    disabled={crewLoading === id}
                    className="px-3 py-1 bg-orange-500/20 text-orange-400 rounded text-xs hover:bg-orange-500/30 disabled:opacity-50"
                  >
                    {crewLoading === id ? '...' : 'Execute'}
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {crew.agents?.slice(0, 4).map((agent, i) => (
                    <span key={i} className="px-2 py-0.5 bg-orange-500/10 text-orange-300 rounded text-xs">
                      {agent.role}
                    </span>
                  ))}
                  {crew.agents?.length > 4 && (
                    <span className="px-2 py-0.5 bg-white/10 text-gray-400 rounded text-xs">
                      +{crew.agents.length - 4} more
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* OODA Loop Panel */}
        <div className="lg:col-span-2 p-5 bg-white/5 rounded-xl border border-white/10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-yellow-500 to-amber-500 flex items-center justify-center">
              <RotateCcw className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold">OODA Loop Automation</h3>
              <p className="text-xs text-gray-500">Observe-Orient-Decide-Act business intelligence cycles</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(oodaCycles.cycles || {}).map(([id, cycle]) => (
              <div key={id} className="p-4 bg-white/5 rounded-lg border border-white/10">
                <div className="flex justify-between items-start mb-3">
                  <h4 className="font-medium text-sm">{cycle.name}</h4>
                  <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-xs">
                    {cycle.frequency}
                  </span>
                </div>
                
                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center text-xs text-blue-400">O</div>
                    <span className="text-xs text-gray-400">{cycle.observe?.length || 0} data sources</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-purple-500/20 flex items-center justify-center text-xs text-purple-400">O</div>
                    <span className="text-xs text-gray-400">{cycle.orient?.length || 0} analysis</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-green-500/20 flex items-center justify-center text-xs text-green-400">D</div>
                    <span className="text-xs text-gray-400">{cycle.decide?.length || 0} decisions</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-orange-500/20 flex items-center justify-center text-xs text-orange-400">A</div>
                    <span className="text-xs text-gray-400">{cycle.act?.length || 0} actions</span>
                  </div>
                </div>

                <button
                  onClick={() => executeOODA(id)}
                  disabled={oodaLoading === id}
                  className="w-full py-2 bg-gradient-to-r from-yellow-500 to-amber-500 rounded-lg text-sm font-medium flex items-center justify-center gap-2 hover:from-yellow-400 hover:to-amber-400 disabled:opacity-50"
                >
                  <Play className="w-4 h-4" />
                  {oodaLoading === id ? 'Starting...' : 'Run Cycle'}
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};


export default OrchestratorCommandCenter;
