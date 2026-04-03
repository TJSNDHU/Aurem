/**
 * AdminActionAI - Admin AI Command Interface
 * ═══════════════════════════════════════════════════════════════════
 * Natural language interface for executing admin actions.
 * © 2025 Reroots Aesthetics Inc. All rights reserved.
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Send, 
  Loader2, 
  DollarSign, 
  Package, 
  ShoppingCart, 
  Tag,
  Clock,
  User,
  CheckCircle2,
  AlertCircle,
  Terminal
} from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Quick action presets
const QUICK_ACTIONS = [
  { label: 'Revenue this week', query: 'Show me revenue for the past 7 days', icon: DollarSign },
  { label: 'Low stock alert', query: 'What products are running low on stock?', icon: Package },
  { label: 'Orders today', query: 'Show me all orders from today', icon: ShoppingCart },
  { label: 'New discount code', query: 'Create a 15% discount code SAVE15 that expires in 7 days', icon: Tag },
];

export default function AdminActionAI() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [actionLog, setActionLog] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Load action log and suggestions on mount
  useEffect(() => {
    loadActionLog();
    loadSuggestions();
  }, []);

  // Scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const loadActionLog = async () => {
    try {
      const response = await fetch(`${API_URL}/api/admin/ai/action/tools`);
      // For now, we'll track actions locally since there's no dedicated log endpoint
    } catch (error) {
      console.error('Failed to load action log:', error);
    }
  };

  const loadSuggestions = async () => {
    try {
      const response = await fetch(`${API_URL}/api/admin/ai/action/suggestions`);
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.suggestions || []);
      }
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    }
  };

  const executeAction = async (query) => {
    if (!query.trim() || isLoading) return;

    setInputValue('');
    setIsLoading(true);

    // Add user message
    const userMessage = {
      role: 'user',
      content: query,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      const response = await fetch(`${API_URL}/api/admin/ai/action/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query })
      });

      const data = await response.json();

      // Add AI response
      const aiMessage = {
        role: 'assistant',
        content: data.summary || data.message || JSON.stringify(data.result, null, 2),
        action: data.action,
        result: data.result,
        success: data.success,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, aiMessage]);

      // Add to action log if an action was taken
      if (data.action && data.action !== 'none') {
        const logEntry = {
          action: data.action,
          query: query,
          success: data.success,
          timestamp: new Date().toISOString(),
          admin: 'Current Admin' // Would come from auth context
        };
        setActionLog(prev => [logEntry, ...prev].slice(0, 20));
      }

    } catch (error) {
      const errorMessage = {
        role: 'assistant',
        content: `Error: ${error.message}`,
        success: false,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeAction(inputValue);
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="h-full flex bg-[#0a0a0c]" data-testid="admin-action-ai">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#C8A96A]/20 flex items-center justify-center">
              <Terminal className="w-5 h-5 text-[#C8A96A]" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Admin Action AI</h2>
              <p className="text-sm text-gray-400">Query data or execute commands in plain English</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="px-6 py-3 border-b border-gray-800 flex gap-2 overflow-x-auto">
          {QUICK_ACTIONS.map((action, index) => (
            <button
              key={index}
              onClick={() => executeAction(action.query)}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm text-gray-300 whitespace-nowrap transition-colors disabled:opacity-50"
              data-testid={`quick-action-${index}`}
            >
              <action.icon className="w-4 h-4 text-[#C8A96A]" />
              {action.label}
            </button>
          ))}
        </div>

        {/* AI Suggestions */}
        {suggestions.length > 0 && messages.length === 0 && (
          <div className="px-6 py-4 border-b border-gray-800">
            <h3 className="text-sm font-medium text-gray-400 mb-2">AI Suggestions</h3>
            <div className="space-y-2">
              {suggestions.map((suggestion, index) => (
                <div
                  key={index}
                  className={`p-3 rounded-lg border ${
                    suggestion.priority === 'high' 
                      ? 'border-red-500/50 bg-red-500/10' 
                      : 'border-yellow-500/50 bg-yellow-500/10'
                  }`}
                >
                  <div className="flex items-center gap-2 text-sm">
                    <AlertCircle className={`w-4 h-4 ${
                      suggestion.priority === 'high' ? 'text-red-400' : 'text-yellow-400'
                    }`} />
                    <span className="text-white">{suggestion.message}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">{suggestion.suggested_action}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Terminal className="w-12 h-12 text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-400 mb-2">
                Admin Action AI Ready
              </h3>
              <p className="text-sm text-gray-500 max-w-md">
                Ask questions about your store or give commands like "Show me revenue this week" 
                or "Create a discount code for 20% off"
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] p-4 rounded-xl ${
                  message.role === 'user'
                    ? 'bg-gray-800 text-white'
                    : message.success === false
                    ? 'bg-red-500/10 border border-red-500/30 text-red-300'
                    : message.action && message.action !== 'none'
                    ? 'bg-[#C8A96A]/10 border border-[#C8A96A]/30 text-[#C8A96A]'
                    : 'bg-gray-800/50 text-white'
                }`}
              >
                {message.action && message.action !== 'none' && (
                  <div className="flex items-center gap-2 mb-2 text-xs text-[#C8A96A]">
                    <CheckCircle2 className="w-3 h-3" />
                    Action: {message.action}
                  </div>
                )}
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                <p className="text-xs text-gray-500 mt-2">
                  {formatTimestamp(message.timestamp)}
                </p>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800/50 p-4 rounded-xl">
                <Loader2 className="w-5 h-5 animate-spin text-[#C8A96A]" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-gray-800">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask anything or give a command..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:border-[#C8A96A] transition-colors disabled:opacity-50"
              data-testid="admin-ai-input"
            />
            <button
              onClick={() => executeAction(inputValue)}
              disabled={isLoading || !inputValue.trim()}
              className="px-4 py-3 bg-[#C8A96A] hover:bg-[#b8995a] rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              data-testid="admin-ai-send"
            >
              <Send className="w-5 h-5 text-black" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Panel - Action Log */}
      <div className="w-80 border-l border-gray-800 flex flex-col">
        <div className="px-4 py-4 border-b border-gray-800">
          <h3 className="font-medium text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#C8A96A]" />
            Action Log
          </h3>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {actionLog.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">
              No actions taken yet
            </p>
          ) : (
            actionLog.map((log, index) => (
              <div
                key={index}
                className="p-3 bg-gray-800/50 rounded-lg border border-gray-700"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-medium ${
                    log.success ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {log.action}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatTimestamp(log.timestamp)}
                  </span>
                </div>
                <p className="text-xs text-gray-400 truncate">{log.query}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                  <User className="w-3 h-3" />
                  {log.admin}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
