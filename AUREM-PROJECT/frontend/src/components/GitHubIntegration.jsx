/**
 * GitHub Integration Components
 * Connect repos, build knowledge base, chat with codebase
 * For commercial AI customization per subscriber company
 */

import React, { useState, useEffect, useRef } from 'react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ═══════════════════════════════════════════════════════════════════════════════
// GITHUB CONNECT BUTTON
// ═══════════════════════════════════════════════════════════════════════════════

export const GitHubConnectButton = ({ 
  companyId, 
  onConnect, 
  className = '' 
}) => {
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const res = await fetch(`${API_URL}/api/github/oauth/start?company_id=${companyId}`);
      const data = await res.json();
      
      if (data.auth_url) {
        // Open GitHub OAuth in popup
        const popup = window.open(
          data.auth_url,
          'github-oauth',
          'width=600,height=700,scrollbars=yes'
        );
        
        // Poll for completion
        const checkClosed = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkClosed);
            setIsConnecting(false);
            onConnect?.();
          }
        }, 500);
      }
    } catch (err) {
      console.error('GitHub connect error:', err);
      setIsConnecting(false);
    }
  };

  return (
    <button
      onClick={handleConnect}
      disabled={isConnecting}
      className={`flex items-center gap-2 px-6 py-3 bg-gray-900 hover:bg-gray-800 text-white rounded-xl font-medium transition-colors disabled:opacity-50 ${className}`}
    >
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
      </svg>
      {isConnecting ? 'Connecting...' : 'Connect GitHub'}
    </button>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// REPO SELECTOR
// ═══════════════════════════════════════════════════════════════════════════════

export const GitHubRepoSelector = ({ 
  companyId, 
  onSelectionChange,
  className = '' 
}) => {
  const [repos, setRepos] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const res = await fetch(`${API_URL}/api/github/repos/${companyId}`);
        if (res.ok) {
          const data = await res.json();
          setRepos(data.repos || []);
          
          // Set initially selected
          const initialSelected = new Set(
            data.repos.filter(r => r.selected).map(r => r.full_name)
          );
          setSelected(initialSelected);
        } else {
          setError('Failed to load repositories');
        }
      } catch (err) {
        setError(err.message);
      }
      setIsLoading(false);
    };

    fetchRepos();
  }, [companyId]);

  const toggleRepo = (fullName) => {
    const newSelected = new Set(selected);
    if (newSelected.has(fullName)) {
      newSelected.delete(fullName);
    } else {
      newSelected.add(fullName);
    }
    setSelected(newSelected);
    onSelectionChange?.(Array.from(newSelected));
  };

  const saveSelection = async () => {
    try {
      await fetch(`${API_URL}/api/github/repos/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          repos: Array.from(selected)
        })
      });
    } catch (err) {
      console.error('Save selection error:', err);
    }
  };

  const filteredRepos = repos.filter(repo =>
    repo.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (repo.description || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="p-8 text-center text-gray-500">
        <div className="animate-spin w-8 h-8 border-4 border-gray-300 border-t-blue-600 rounded-full mx-auto mb-2" />
        Loading repositories...
      </div>
    );
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>;
  }

  return (
    <div className={className}>
      {/* Search */}
      <div className="mb-4">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search repositories..."
          className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Repo list */}
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {filteredRepos.map((repo) => (
          <div
            key={repo.full_name}
            onClick={() => toggleRepo(repo.full_name)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              selected.has(repo.full_name)
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="flex items-start gap-3">
              <div className={`w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 ${
                selected.has(repo.full_name)
                  ? 'border-blue-500 bg-blue-500'
                  : 'border-gray-300'
              }`}>
                {selected.has(repo.full_name) && (
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium truncate">{repo.name}</span>
                  {repo.private && (
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">Private</span>
                  )}
                  {repo.language && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded">{repo.language}</span>
                  )}
                </div>
                {repo.description && (
                  <p className="text-sm text-gray-500 truncate mt-1">{repo.description}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm text-gray-500">
          {selected.size} repositories selected
        </span>
        <button
          onClick={saveSelection}
          disabled={selected.size === 0}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          Save Selection
        </button>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// KNOWLEDGE BASE BUILDER
// ═══════════════════════════════════════════════════════════════════════════════

export const KnowledgeBaseBuilder = ({ companyId, onComplete }) => {
  const [status, setStatus] = useState(null);
  const [isIngesting, setIsIngesting] = useState(false);
  const [progress, setProgress] = useState([]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/github/status/${companyId}`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        }
      } catch (err) {
        console.error(err);
      }
    };

    fetchStatus();
  }, [companyId]);

  const startIngestion = async () => {
    if (!status?.selected_repos?.length) return;

    setIsIngesting(true);
    setProgress([]);

    try {
      const res = await fetch(`${API_URL}/api/github/ingest/all?company_id=${companyId}`, {
        method: 'POST'
      });
      
      if (res.ok) {
        const data = await res.json();
        setProgress(data.results || []);
        onComplete?.();
      }
    } catch (err) {
      console.error(err);
    }
    
    setIsIngesting(false);
  };

  return (
    <div className="space-y-6">
      {/* Status */}
      <div className="p-4 rounded-xl bg-gray-50">
        <h4 className="font-medium mb-2">Knowledge Base Status</h4>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Selected Repos:</span>
            <span className="ml-2 font-medium">{status?.selected_repos?.length || 0}</span>
          </div>
          <div>
            <span className="text-gray-500">Documents:</span>
            <span className="ml-2 font-medium">{status?.knowledge_base_docs || 0}</span>
          </div>
        </div>
      </div>

      {/* Selected repos */}
      {status?.selected_repos?.length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Repositories to Ingest</h4>
          <div className="space-y-2">
            {status.selected_repos.map((repo) => (
              <div key={repo.repo_full_name} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <span className="font-mono text-sm">{repo.repo_full_name}</span>
                {repo.ingested ? (
                  <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded">
                    {repo.file_count} files
                  </span>
                ) : (
                  <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs rounded">
                    Pending
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress */}
      {progress.length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Ingestion Results</h4>
          <div className="space-y-2">
            {progress.map((result, idx) => (
              <div key={idx} className={`p-3 rounded-lg ${
                result.status === 'success' ? 'bg-green-50' : 'bg-red-50'
              }`}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{result.repo}</span>
                  {result.status === 'success' ? (
                    <span className="text-green-600">{result.files} files</span>
                  ) : (
                    <span className="text-red-600">Error</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action */}
      <button
        onClick={startIngestion}
        disabled={isIngesting || !status?.selected_repos?.length}
        className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {isIngesting ? (
          <span className="flex items-center justify-center gap-2">
            <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
            Building Knowledge Base...
          </span>
        ) : (
          'Build Knowledge Base'
        )}
      </button>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// GITHUB CHATBOT
// ═══════════════════════════════════════════════════════════════════════════════

export const GitHubChatbot = ({ 
  companyId, 
  title = "Ask about your codebase",
  className = '' 
}) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/github/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_id: companyId,
          message: userMessage,
          session_id: sessionId
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response,
          sources: data.sources
        }]);
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please try again.',
          error: true
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        error: true
      }]);
    }

    setIsLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className={`flex flex-col h-[500px] border border-gray-200 rounded-2xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-gray-900 to-gray-800 text-white flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
        </div>
        <div>
          <h3 className="font-medium">{title}</h3>
          <p className="text-xs text-white/60">Powered by your GitHub repos</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p>Ask questions about your codebase</p>
            <p className="text-sm mt-1">e.g., "How does the authentication work?"</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-br-sm'
                : msg.error
                  ? 'bg-red-100 text-red-800 rounded-bl-sm'
                  : 'bg-white border border-gray-200 rounded-bl-sm'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              
              {msg.sources?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-500 mb-1">Sources:</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.sources.map((src, i) => (
                      <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded font-mono">
                        {src.split('/').pop()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about your codebase..."
            disabled={isLoading}
            className="flex-1 px-4 py-2 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════════════════════
// FULL INTEGRATION PANEL
// ═══════════════════════════════════════════════════════════════════════════════

export const GitHubIntegrationPanel = ({ companyId }) => {
  const [status, setStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('connect');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/github/status/${companyId}`);
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
          
          // Auto-select appropriate tab
          if (data.connected && data.knowledge_base_docs > 0) {
            setActiveTab('chat');
          } else if (data.connected) {
            setActiveTab('repos');
          }
        }
      } catch (err) {
        console.error(err);
      }
      setIsLoading(false);
    };

    fetchStatus();
  }, [companyId]);

  const refreshStatus = async () => {
    const res = await fetch(`${API_URL}/api/github/status/${companyId}`);
    if (res.ok) {
      const data = await res.json();
      setStatus(data);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center">
        <div className="animate-spin w-10 h-10 border-4 border-gray-300 border-t-blue-600 rounded-full mx-auto" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 rounded-xl bg-gray-900 flex items-center justify-center">
          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
          </svg>
        </div>
        <div>
          <h2 className="text-xl font-bold">GitHub Integration</h2>
          <p className="text-gray-500">Connect your repos to build an AI knowledge base</p>
        </div>
        
        {status?.connected && (
          <div className="ml-auto flex items-center gap-2">
            <img src={status.avatar_url} alt="" className="w-8 h-8 rounded-full" />
            <span className="font-medium">{status.github_user}</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-6">
        {['connect', 'repos', 'build', 'chat'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        {activeTab === 'connect' && (
          <div className="text-center py-8">
            {status?.connected ? (
              <>
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium mb-2">GitHub Connected</h3>
                <p className="text-gray-500 mb-4">Connected as @{status.github_user}</p>
                <button
                  onClick={() => setActiveTab('repos')}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Select Repositories
                </button>
              </>
            ) : (
              <>
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
                  <svg className="w-8 h-8 text-gray-400" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium mb-2">Connect GitHub</h3>
                <p className="text-gray-500 mb-6">
                  Connect your GitHub account to let AI learn from your repositories
                </p>
                <GitHubConnectButton 
                  companyId={companyId} 
                  onConnect={refreshStatus}
                />
              </>
            )}
          </div>
        )}

        {activeTab === 'repos' && (
          <GitHubRepoSelector 
            companyId={companyId}
            onSelectionChange={() => refreshStatus()}
          />
        )}

        {activeTab === 'build' && (
          <KnowledgeBaseBuilder 
            companyId={companyId}
            onComplete={refreshStatus}
          />
        )}

        {activeTab === 'chat' && (
          <GitHubChatbot companyId={companyId} />
        )}
      </div>
    </div>
  );
};


export default {
  GitHubConnectButton,
  GitHubRepoSelector,
  KnowledgeBaseBuilder,
  GitHubChatbot,
  GitHubIntegrationPanel
};
