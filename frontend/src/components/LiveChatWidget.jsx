/**
 * ORA Live Chat Widget
 * Floating chat bubble for the aurem.live landing page.
 * Routes visitor messages through the Sovereign Brain via /api/comms/chat
 */
import React, { useState, useRef, useEffect } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || window.location.origin;

export default function LiveChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [showEmail, setShowEmail] = useState(false);
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [emailSent, setEmailSent] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Show email capture after 2 messages
  useEffect(() => {
    const userMsgs = messages.filter(m => m.role === 'user');
    if (userMsgs.length >= 2 && !emailSent && !email) setShowEmail(true);
  }, [messages, emailSent, email]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const text = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setSending(true);

    try {
      const res = await fetch(`${API}/api/comms/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          visitor_name: name || undefined,
          visitor_email: email || undefined,
          page_url: window.location.href,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (!sessionId) setSessionId(data.session_id);
        setMessages(prev => [...prev, { role: 'assistant', content: data.response, source: data.source }]);
      } else {
        setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I had trouble processing that. Please try again.' }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Connection issue. Please try again in a moment.' }]);
    }
    setSending(false);
  };

  const submitEmail = () => {
    if (email.trim()) {
      setEmailSent(true);
      setShowEmail(false);
      // Re-send last message context with email for lead capture
      fetch(`${API}/api/comms/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: '[Lead captured]',
          session_id: sessionId,
          visitor_name: name,
          visitor_email: email,
        }),
      }).catch(() => {});
    }
  };

  return (
    <>
      {/* Floating Bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          data-testid="chat-bubble"
          style={{
            position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
            width: 56, height: 56, borderRadius: '50%',
            background: 'linear-gradient(135deg, #D4AF37, #8B6914)',
            border: 'none', cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(212,175,55,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'transform 0.2s',
          }}
          onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.1)'}
          onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#050507" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </button>
      )}

      {/* Chat Window */}
      {open && (
        <div data-testid="chat-window" style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
          width: 360, maxWidth: 'calc(100vw - 32px)', height: 500, maxHeight: 'calc(100vh - 48px)',
          borderRadius: 16, overflow: 'hidden',
          background: '#0A0A12', border: '1px solid rgba(212,175,55,0.2)',
          boxShadow: '0 8px 40px rgba(0,0,0,0.6)',
          display: 'flex', flexDirection: 'column',
          fontFamily: "'Jost', -apple-system, sans-serif",
        }}>
          {/* Header */}
          <div style={{
            padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: 'linear-gradient(135deg, rgba(212,175,55,0.12), rgba(139,105,20,0.08))',
            borderBottom: '1px solid rgba(212,175,55,0.15)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'linear-gradient(135deg, #D4AF37, #8B6914)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, fontWeight: 700, color: '#050507',
              }}>A</div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#E8E0D0' }}>ORA Assistant</div>
                <div style={{ fontSize: 9, color: '#4ADE80', letterSpacing: '0.1em' }}>
                  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#4ADE80', marginRight: 4, verticalAlign: 'middle' }}/>
                  ONLINE
                </div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} style={{
              background: 'none', border: 'none', cursor: 'pointer', color: '#666', fontSize: 18, padding: 4,
            }} data-testid="chat-close">x</button>
          </div>

          {/* Messages */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '30px 16px' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12, margin: '0 auto 12px',
                    background: 'linear-gradient(135deg, #D4AF37, #8B6914)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 20, fontWeight: 700, color: '#050507',
                  }}>A</div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#E8E0D0', marginBottom: 4 }}>Welcome to AUREM</div>
                <div style={{ fontSize: 11, color: '#666', lineHeight: 1.5 }}>
                  I'm ORA, your AI business assistant. Ask me about website optimization, pricing, or get a free system scan.
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 10,
              }}>
                <div style={{
                  maxWidth: '80%', padding: '10px 14px', borderRadius: 12,
                  fontSize: 12, lineHeight: 1.5,
                  ...(msg.role === 'user'
                    ? { background: 'linear-gradient(135deg, #D4AF37, #A08028)', color: '#050507', borderBottomRightRadius: 4 }
                    : { background: 'rgba(255,255,255,0.06)', color: '#E8E0D0', borderBottomLeftRadius: 4 }),
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {sending && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 10 }}>
                <div style={{
                  padding: '10px 14px', borderRadius: 12,
                  background: 'rgba(255,255,255,0.06)', color: '#888',
                  fontSize: 12, fontStyle: 'italic',
                }}>
                  ORA is thinking…
                </div>
              </div>
            )}

            {/* Email Capture */}
            {showEmail && !emailSent && (
              <div style={{
                padding: 14, borderRadius: 12, marginBottom: 10,
                background: 'rgba(212,175,55,0.08)', border: '1px solid rgba(212,175,55,0.2)',
              }} data-testid="email-capture">
                <div style={{ fontSize: 11, fontWeight: 600, color: '#D4AF37', marginBottom: 8 }}>
                  Want me to follow up? Leave your details:
                </div>
                <input
                  value={name} onChange={e => setName(e.target.value)}
                  placeholder="Your name" data-testid="chat-name-input"
                  style={{
                    width: '100%', padding: '8px 10px', borderRadius: 8, fontSize: 11, marginBottom: 6,
                    background: '#0A0A12', border: '1px solid rgba(212,175,55,0.15)', color: '#E8E0D0',
                    boxSizing: 'border-box',
                  }}
                />
                <input
                  value={email} onChange={e => setEmail(e.target.value)}
                  placeholder="your@email.com" type="email" data-testid="chat-email-input"
                  style={{
                    width: '100%', padding: '8px 10px', borderRadius: 8, fontSize: 11, marginBottom: 8,
                    background: '#0A0A12', border: '1px solid rgba(212,175,55,0.15)', color: '#E8E0D0',
                    boxSizing: 'border-box',
                  }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={submitEmail} data-testid="chat-submit-email" style={{
                    flex: 1, padding: '8px', borderRadius: 8, border: 'none', cursor: 'pointer',
                    background: 'linear-gradient(135deg, #D4AF37, #8B6914)', color: '#050507',
                    fontSize: 11, fontWeight: 700,
                  }}>Send</button>
                  <button onClick={() => setShowEmail(false)} style={{
                    padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)',
                    background: 'none', color: '#666', fontSize: 11, cursor: 'pointer',
                  }}>Skip</button>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{
            padding: '10px 14px', borderTop: '1px solid rgba(255,255,255,0.06)',
            display: 'flex', gap: 8,
          }}>
            <input
              value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              placeholder="Ask ORA anything..."
              data-testid="chat-input"
              style={{
                flex: 1, padding: '10px 14px', borderRadius: 10, fontSize: 12,
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
                color: '#E8E0D0', outline: 'none',
              }}
            />
            <button
              onClick={sendMessage} disabled={sending || !input.trim()}
              data-testid="chat-send"
              style={{
                padding: '10px 16px', borderRadius: 10, border: 'none', cursor: 'pointer',
                background: sending || !input.trim() ? '#333' : 'linear-gradient(135deg, #D4AF37, #8B6914)',
                color: '#050507', fontSize: 12, fontWeight: 700,
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
