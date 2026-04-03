/**
 * SupportChat.jsx - AI-First Support System
 * 
 * Flow:
 * 1. AI chatbot tries to resolve issue
 * 2. If AI can't help → User requests callback
 * 3. Admin can send screen share request to user
 */

import React, { useState, useRef, useEffect } from 'react';

const C = {
  void: "#060608",
  gold: "#c9a86e",
  goldDim: "rgba(201,168,110,0.6)",
  surface: "#0f0f11",
  surface2: "#151518",
  text: "#f5f0e8",
  textDim: "rgba(245,240,232,0.5)",
  border: "rgba(201,168,110,0.15)",
  red: "#ef4444",
  green: "#22c55e",
  blue: "#3b82f6"
};

// Common FAQ topics for quick replies
const QUICK_TOPICS = [
  { id: 'order', label: 'Order Status', icon: '📦' },
  { id: 'return', label: 'Returns & Refunds', icon: '↩️' },
  { id: 'product', label: 'Product Info', icon: '🧴' },
  { id: 'account', label: 'Account Help', icon: '👤' },
];

export default function SupportChat({ user, apiBase, onClose, onRequestScreenShare }) {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      text: `Hi ${user?.name?.split(' ')[0] || 'there'}! I'm ReRoots AI Assistant. How can I help you today?`,
      time: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showCallbackForm, setShowCallbackForm] = useState(false);
  const [callbackRequested, setCallbackRequested] = useState(false);
  const [callbackPhone, setCallbackPhone] = useState('');
  const [callbackNote, setCallbackNote] = useState('');
  const [screenShareRequest, setScreenShareRequest] = useState(null);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  // Connect to support WebSocket for admin notifications
  useEffect(() => {
    if (!user?.id) return;
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = apiBase.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${wsHost}/api/support/ws/chat/${user.id}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'screen_share_request') {
          // Admin is requesting screen share
          setScreenShareRequest({
            admin_name: data.admin_name || 'Support Team',
            session_id: data.session_id,
            message: data.message || 'Our support team would like to view your screen to help diagnose the issue.'
          });
        }
      };
      
      ws.onerror = () => console.log('[SupportChat] WebSocket error');
      ws.onclose = () => console.log('[SupportChat] WebSocket closed');
    } catch (e) {
      console.log('[SupportChat] WebSocket connection failed');
    }
    
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [user?.id, apiBase]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send message to AI
  const sendMessage = async (text) => {
    if (!text.trim()) return;
    
    const userMsg = {
      id: Date.now(),
      type: 'user',
      text: text.trim(),
      time: new Date()
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);
    
    try {
      const res = await fetch(`${apiBase}/api/support/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id,
          user_name: user?.name || user?.email,
          message: text.trim(),
          context: messages.slice(-5).map(m => ({ role: m.type === 'user' ? 'user' : 'assistant', content: m.text }))
        })
      });
      
      const data = await res.json();
      
      const botMsg = {
        id: Date.now() + 1,
        type: 'bot',
        text: data.response || "I'm sorry, I couldn't process that. Would you like to speak with our team?",
        time: new Date(),
        showCallback: data.show_callback || false
      };
      
      setMessages(prev => [...prev, botMsg]);
      
      // If AI suggests callback, show the option
      if (data.show_callback) {
        setTimeout(() => setShowCallbackForm(true), 500);
      }
      
    } catch (e) {
      console.error('[SupportChat] Error:', e);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        type: 'bot',
        text: "I'm having trouble connecting right now. Would you like to request a callback from our team?",
        time: new Date(),
        showCallback: true
      }]);
      setShowCallbackForm(true);
    } finally {
      setIsTyping(false);
    }
  };

  // Handle quick topic click
  const handleQuickTopic = (topic) => {
    const questions = {
      order: "I need help with my order status",
      return: "I want to know about returns and refunds",
      product: "I have a question about your products",
      account: "I need help with my account"
    };
    sendMessage(questions[topic.id] || topic.label);
  };

  // Request callback
  const requestCallback = async () => {
    try {
      await fetch(`${apiBase}/api/support/callback/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user?.id,
          user_name: user?.name || user?.email,
          user_email: user?.email,
          phone: callbackPhone,
          note: callbackNote,
          chat_history: messages.map(m => ({ role: m.type, content: m.text }))
        })
      });
      
      setCallbackRequested(true);
      setShowCallbackForm(false);
      
      setMessages(prev => [...prev, {
        id: Date.now(),
        type: 'bot',
        text: "Great! Our team will call you back shortly. You'll also receive a notification when they're ready to help.",
        time: new Date()
      }]);
      
    } catch (e) {
      console.error('[SupportChat] Callback request error:', e);
    }
  };

  // Accept screen share request from admin
  const acceptScreenShare = () => {
    if (screenShareRequest && onRequestScreenShare) {
      onRequestScreenShare(screenShareRequest.session_id);
    }
    setScreenShareRequest(null);
  };

  // Decline screen share request
  const declineScreenShare = async () => {
    if (screenShareRequest) {
      try {
        await fetch(`${apiBase}/api/support/screen-share/decline`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: screenShareRequest.session_id,
            user_id: user?.id
          })
        });
      } catch (e) {}
    }
    setScreenShareRequest(null);
  };

  return (
    <div style={{
      position: 'fixed', bottom: 90, right: 12, width: 'calc(100% - 24px)', maxWidth: 340, height: 'calc(100vh - 180px)', maxHeight: 460,
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 16,
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)', zIndex: 9999,
      display: 'flex', flexDirection: 'column', overflow: 'hidden'
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px', borderBottom: `1px solid ${C.border}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'linear-gradient(135deg, rgba(201,168,110,0.1), transparent)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={C.void} strokeWidth="2">
              <circle cx="12" cy="12" r="3"/>
              <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
            </svg>
          </div>
          <div>
            <div style={{ color: C.text, fontWeight: 600, fontSize: 14 }}>ReRoots Support</div>
            <div style={{ color: C.green, fontSize: 11, display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: C.green }} />
              AI Assistant Online
            </div>
          </div>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: C.textDim,
          cursor: 'pointer', fontSize: 20, padding: '0 4px'
        }}>×</button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{
            display: 'flex',
            justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: 12
          }}>
            <div style={{
              maxWidth: '80%',
              padding: '10px 14px',
              borderRadius: msg.type === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
              background: msg.type === 'user' 
                ? `linear-gradient(135deg, ${C.gold}, #b8956a)`
                : C.surface2,
              color: msg.type === 'user' ? C.void : C.text,
              fontSize: 13,
              lineHeight: 1.5
            }}>
              {msg.text}
            </div>
          </div>
        ))}
        
        {/* Typing indicator */}
        {isTyping && (
          <div style={{ display: 'flex', gap: 4, padding: '10px 14px' }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{
                width: 8, height: 8, borderRadius: '50%', background: C.textDim,
                animation: `bounce 1.4s ease-in-out ${i * 0.16}s infinite`
              }} />
            ))}
          </div>
        )}
        
        {/* Quick topics (show at start) */}
        {messages.length === 1 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ color: C.textDim, fontSize: 11, marginBottom: 8 }}>Quick topics:</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {QUICK_TOPICS.map(topic => (
                <button key={topic.id} onClick={() => handleQuickTopic(topic)} style={{
                  padding: '8px 12px', background: C.surface2,
                  border: `1px solid ${C.border}`, borderRadius: 20,
                  color: C.text, fontSize: 12, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 6,
                  transition: 'all 0.2s'
                }}>
                  <span>{topic.icon}</span>
                  {topic.label}
                </button>
              ))}
            </div>
          </div>
        )}
        
        {/* Callback form */}
        {showCallbackForm && !callbackRequested && (
          <div style={{
            background: C.surface2, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: 14, marginTop: 12
          }}>
            <div style={{ color: C.text, fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
              Request a Callback
            </div>
            <div style={{ color: C.textDim, fontSize: 12, marginBottom: 12 }}>
              Our team will call you back within 15 minutes.
            </div>
            <input
              type="tel"
              placeholder="Phone number (optional)"
              value={callbackPhone}
              onChange={(e) => setCallbackPhone(e.target.value)}
              style={{
                width: '100%', padding: '10px 12px', background: C.void,
                border: `1px solid ${C.border}`, borderRadius: 8,
                color: C.text, fontSize: 13, marginBottom: 8, outline: 'none'
              }}
            />
            <textarea
              placeholder="Briefly describe your issue..."
              value={callbackNote}
              onChange={(e) => setCallbackNote(e.target.value)}
              rows={2}
              style={{
                width: '100%', padding: '10px 12px', background: C.void,
                border: `1px solid ${C.border}`, borderRadius: 8,
                color: C.text, fontSize: 13, marginBottom: 12, outline: 'none',
                resize: 'none'
              }}
            />
            <button onClick={requestCallback} style={{
              width: '100%', padding: '10px 16px',
              background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
              color: C.void, border: 'none', borderRadius: 8,
              fontWeight: 600, fontSize: 13, cursor: 'pointer'
            }}>
              Request Callback
            </button>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '12px 16px', borderTop: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            type="text"
            placeholder="Type your message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage(input)}
            style={{
              flex: 1, padding: '10px 14px', background: C.surface2,
              border: `1px solid ${C.border}`, borderRadius: 24,
              color: C.text, fontSize: 13, outline: 'none'
            }}
          />
          <button onClick={() => sendMessage(input)} disabled={!input.trim()} style={{
            width: 40, height: 40, borderRadius: '50%',
            background: input.trim() ? `linear-gradient(135deg, ${C.gold}, #b8956a)` : C.surface2,
            border: 'none', cursor: input.trim() ? 'pointer' : 'default',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={input.trim() ? C.void : C.textDim} strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        
        {!callbackRequested && (
          <button onClick={() => setShowCallbackForm(true)} style={{
            width: '100%', marginTop: 8, padding: '8px',
            background: 'transparent', border: `1px solid ${C.border}`,
            borderRadius: 8, color: C.textDim, fontSize: 11,
            cursor: 'pointer', display: 'flex', alignItems: 'center',
            justifyContent: 'center', gap: 6
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
            </svg>
            Need to talk? Request a callback
          </button>
        )}
      </div>

      {/* Screen Share Request Popup from Admin */}
      {screenShareRequest && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.85)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: 20, zIndex: 10
        }}>
          <div style={{
            background: C.surface, border: `1px solid ${C.gold}`,
            borderRadius: 16, padding: 24, maxWidth: 300, textAlign: 'center'
          }}>
            <div style={{
              width: 50, height: 50, borderRadius: '50%', margin: '0 auto 16px',
              background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={C.void} strokeWidth="2">
                <rect x="2" y="3" width="20" height="14" rx="2"/>
                <line x1="8" y1="21" x2="16" y2="21"/>
                <line x1="12" y1="17" x2="12" y2="21"/>
              </svg>
            </div>
            <div style={{ color: C.text, fontWeight: 600, fontSize: 16, marginBottom: 8 }}>
              Screen Share Request
            </div>
            <div style={{ color: C.textDim, fontSize: 13, marginBottom: 20, lineHeight: 1.5 }}>
              <strong style={{ color: C.gold }}>{screenShareRequest.admin_name}</strong> would like to view your screen to help resolve your issue.
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={declineScreenShare} style={{
                flex: 1, padding: '10px 16px', background: 'transparent',
                border: `1px solid ${C.border}`, borderRadius: 8,
                color: C.textDim, fontSize: 13, cursor: 'pointer'
              }}>
                Decline
              </button>
              <button onClick={acceptScreenShare} style={{
                flex: 1, padding: '10px 16px',
                background: `linear-gradient(135deg, ${C.gold}, #b8956a)`,
                border: 'none', borderRadius: 8,
                color: C.void, fontWeight: 600, fontSize: 13, cursor: 'pointer'
              }}>
                Allow
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
