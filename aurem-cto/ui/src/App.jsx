import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || window.location.origin;

function App() {
  const [health, setHealth] = useState(null);
  const [tools, setTools] = useState([]);
  const [outboxStats, setOutboxStats] = useState({ pending: 0, processed: 0, failed: 0 });
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/health`);
        setHealth(res.data.ok ? 'online' : 'degraded');
      } catch {
        setHealth('offline');
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchTools = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/tools/list`);
        setTools(res.data.tools || []);
      } catch (err) {
        console.error('Failed to fetch tools:', err);
      }
    };
    fetchTools();
  }, []);

  useEffect(() => {
    const fetchOutbox = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/outbox/stats`);
        setOutboxStats(res.data.stats || { pending: 0, processed: 0, failed: 0 });
      } catch (err) {
        console.error('Failed to fetch outbox stats:', err);
      }
    };
    fetchOutbox();
    const interval = setInterval(fetchOutbox, 15000);
    return () => clearInterval(interval);
  }, []);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const token = localStorage.getItem('admin_token');
      const res = await axios.post(
        `${API_BASE}/api/chat`,
        { prompt: input, max_tool_iters: 4 },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const oraMsg = {
        role: 'ora',
        content: res.data.content,
        provider: res.data.provider,
        iters: res.data.iterations
      };
      setMessages(prev => [...prev, oraMsg]);
    } catch (err) {
      const errMsg = {
        role: 'ora',
        content: `Error: ${err.response?.data?.error || err.message}`,
        provider: null,
        iters: null
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="bg-slate-900 border-b border-slate-800 p-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-amber-400">ORA CTO Sovereign — cto.aurem.live</h1>
        <div
          data-testid="health-badge"
          className={`px-3 py-1 rounded-full text-sm font-semibold ${
            health === 'online' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          {health === 'online' ? 'API Online' : 'API Offline'}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 bg-slate-900 border-r border-slate-800 overflow-y-auto p-4">
          <h2 className="text-lg font-semibold mb-3 text-amber-400">Tools ({tools.length})</h2>
          <ul data-testid="tools-list" className="space-y-1">
            {tools.map((tool, idx) => (
              <li key={idx} className="text-sm text-slate-300 hover:text-amber-400 cursor-default">
                {tool}
              </li>
            ))}
          </ul>
        </aside>

        <main className="flex-1 flex flex-col p-6 overflow-hidden">
          <div data-testid="chat-container" className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.length === 0 && (
              <div className="text-center text-slate-500 mt-12">
                {health === 'offline' ? 'API offline — waiting...' : 'Start a conversation with ORA CTO'}
              </div>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                data-testid={`message-${msg.role}`}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-2xl px-4 py-2 rounded-lg ${
                    msg.role === 'user'
                      ? 'bg-amber-600 text-slate-950'
                      : 'bg-slate-800 text-slate-100'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                  {msg.provider && (
                    <div className="text-xs mt-1 opacity-70">
                      {msg.provider} • {msg.iters} iters
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <textarea
              data-testid="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask ORA CTO..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 focus:outline-none focus:border-amber-400 resize-none"
              rows={3}
              disabled={loading}
            />
            <button
              data-testid="send-button"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-slate-950 font-semibold px-6 rounded-lg transition-colors"
            >
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </main>

        <aside className="w-64 bg-slate-900 border-l border-slate-800 p-4">
          <h2 className="text-lg font-semibold mb-3 text-amber-400">Outbox Stats</h2>
          <div data-testid="outbox-stats" className="space-y-4">
            <div className="bg-slate-800 rounded-lg p-4 text-center">
              <div className="text-3xl font-bold text-yellow-400">{outboxStats.pending}</div>
              <div className="text-sm text-slate-400 mt-1">Pending</div>
            </div>
            <div className="bg-slate-800 rounded-lg p-4 text-center">
              <div className="text-3xl font-bold text-green-400">{outboxStats.processed}</div>
              <div className="text-sm text-slate-400 mt-1">Processed</div>
            </div>
            <div className="bg-slate-800 rounded-lg p-4 text-center">
              <div className="text-3xl font-bold text-red-400">{outboxStats.failed}</div>
              <div className="text-sm text-slate-400 mt-1">Failed</div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;