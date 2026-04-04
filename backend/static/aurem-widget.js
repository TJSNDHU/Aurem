/**
 * AUREM Chat Widget - Embeddable for Any Website
 * Full-featured AI chat bubble with ORA integration
 */

(function() {
  'use strict';

  // Configuration
  const AUREM_CONFIG = {
    apiUrl: 'https://live-support-3.preview.emergentagent.com/api',
    businessId: null, // Will be set during initialization
    theme: {
      primaryColor: '#D4AF37',
      accentColor: '#64C8FF',
      backgroundColor: '#0A0F23',
      textColor: '#F4F4F4'
    },
    position: 'bottom-right', // bottom-right, bottom-left, top-right, top-left
    greeting: 'Hi! How can AUREM help your business today?',
    placeholder: 'Ask me anything...',
    enableVoice: true,
    enableBooking: true,
    enableLeadCapture: true
  };

  // Create widget HTML
  const createWidget = () => {
    const widgetHTML = `
      <div id="aurem-widget" style="
        position: fixed;
        ${AUREM_CONFIG.position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
        ${AUREM_CONFIG.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
        z-index: 999999;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      ">
        <!-- Chat Bubble Button -->
        <button id="aurem-bubble" style="
          width: 60px;
          height: 60px;
          border-radius: 50%;
          background: linear-gradient(135deg, ${AUREM_CONFIG.theme.primaryColor} 0%, #8B7355 100%);
          border: none;
          cursor: pointer;
          box-shadow: 0 4px 20px rgba(212, 175, 55, 0.4);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.3s;
          position: relative;
        ">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#050505" stroke-width="2">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
          <span id="aurem-notification-badge" style="
            position: absolute;
            top: -5px;
            right: -5px;
            width: 22px;
            height: 22px;
            background: #ef4444;
            border-radius: 50%;
            display: none;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 11px;
            font-weight: 600;
          ">1</span>
        </button>

        <!-- Chat Window -->
        <div id="aurem-chat-window" style="
          width: 380px;
          height: 600px;
          background: ${AUREM_CONFIG.theme.backgroundColor};
          border-radius: 16px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
          display: none;
          flex-direction: column;
          overflow: hidden;
          margin-bottom: 15px;
        ">
          <!-- Header -->
          <div style="
            background: linear-gradient(135deg, ${AUREM_CONFIG.theme.primaryColor} 0%, #8B7355 100%);
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
          ">
            <div style="display: flex; align-items: center; gap: 12px;">
              <div style="
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.2);
                display: flex;
                align-items: center;
                justify-content: center;
              ">
                <span style="font-size: 20px;">✨</span>
              </div>
              <div>
                <div style="color: #050505; font-weight: 600; font-size: 16px; letter-spacing: 0.1em;">ORA</div>
                <div style="color: rgba(0, 0, 0, 0.7); font-size: 11px; letter-spacing: 0.05em;">AI Business Assistant</div>
              </div>
            </div>
            <button id="aurem-close" style="
              width: 32px;
              height: 32px;
              border-radius: 50%;
              background: rgba(0, 0, 0, 0.1);
              border: none;
              cursor: pointer;
              display: flex;
              align-items: center;
              justify-content: center;
            ">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#050505" stroke-width="2">
                <path d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <!-- Messages Container -->
          <div id="aurem-messages" style="
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
          ">
            <!-- Greeting Message -->
            <div style="
              align-self: flex-start;
              max-width: 85%;
            ">
              <div style="
                background: linear-gradient(135deg, rgba(100, 200, 255, 0.15), rgba(100, 200, 255, 0.05));
                border: 1px solid rgba(100, 200, 255, 0.2);
                border-radius: 16px 16px 16px 4px;
                padding: 12px 16px;
                color: ${AUREM_CONFIG.theme.textColor};
                font-size: 14px;
                line-height: 1.5;
              ">${AUREM_CONFIG.greeting}</div>
              <div style="
                font-size: 9px;
                color: rgba(255, 255, 255, 0.3);
                margin-top: 4px;
                letter-spacing: 0.05em;
              ">ORA • Just now</div>
            </div>

            <!-- Quick Actions -->
            <div id="aurem-quick-actions" style="
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 8px;
              margin-top: 8px;
            ">
              <button class="aurem-quick-btn" data-action="book" style="
                padding: 12px;
                background: rgba(212, 175, 55, 0.1);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px;
                color: ${AUREM_CONFIG.theme.primaryColor};
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
              ">📅 Book Meeting</button>
              <button class="aurem-quick-btn" data-action="pricing" style="
                padding: 12px;
                background: rgba(212, 175, 55, 0.1);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px;
                color: ${AUREM_CONFIG.theme.primaryColor};
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
              ">💰 View Pricing</button>
              <button class="aurem-quick-btn" data-action="demo" style="
                padding: 12px;
                background: rgba(212, 175, 55, 0.1);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px;
                color: ${AUREM_CONFIG.theme.primaryColor};
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
              ">🎥 Watch Demo</button>
              <button class="aurem-quick-btn" data-action="help" style="
                padding: 12px;
                background: rgba(212, 175, 55, 0.1);
                border: 1px solid rgba(212, 175, 55, 0.3);
                border-radius: 8px;
                color: ${AUREM_CONFIG.theme.primaryColor};
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
              ">💬 Live Support</button>
            </div>
          </div>

          <!-- Typing Indicator -->
          <div id="aurem-typing" style="
            padding: 12px 20px;
            display: none;
            align-items: center;
            gap: 8px;
          ">
            <div style="display: flex; gap: 4px;">
              <div style="width: 6px; height: 6px; border-radius: 50%; background: ${AUREM_CONFIG.theme.primaryColor}; animation: aurem-bounce 1.4s infinite ease-in-out;"></div>
              <div style="width: 6px; height: 6px; border-radius: 50%; background: ${AUREM_CONFIG.theme.primaryColor}; animation: aurem-bounce 1.4s infinite ease-in-out 0.2s;"></div>
              <div style="width: 6px; height: 6px; border-radius: 50%; background: ${AUREM_CONFIG.theme.primaryColor}; animation: aurem-bounce 1.4s infinite ease-in-out 0.4s;"></div>
            </div>
            <span style="color: rgba(255, 255, 255, 0.5); font-size: 11px;">ORA is typing...</span>
          </div>

          <!-- Input Area -->
          <div style="
            padding: 16px 20px;
            border-top: 1px solid rgba(100, 150, 255, 0.1);
            background: rgba(10, 15, 35, 0.8);
          ">
            <div style="
              display: flex;
              gap: 8px;
              align-items: center;
              padding: 10px 14px;
              background: rgba(100, 200, 255, 0.05);
              border: 1px solid rgba(100, 200, 255, 0.2);
              border-radius: 10px;
            ">
              <input 
                id="aurem-input" 
                type="text" 
                placeholder="${AUREM_CONFIG.placeholder}"
                style="
                  flex: 1;
                  background: none;
                  border: none;
                  outline: none;
                  color: ${AUREM_CONFIG.theme.textColor};
                  font-size: 14px;
                "
              />
              ${AUREM_CONFIG.enableVoice ? `
              <button id="aurem-voice-btn" style="
                width: 36px;
                height: 36px;
                border-radius: 50%;
                background: rgba(100, 200, 255, 0.1);
                border: 1px solid rgba(100, 200, 255, 0.3);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
              ">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="${AUREM_CONFIG.theme.accentColor}" stroke-width="2">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
              </button>
              ` : ''}
              <button id="aurem-send-btn" style="
                width: 36px;
                height: 36px;
                border-radius: 50%;
                background: linear-gradient(135deg, ${AUREM_CONFIG.theme.accentColor} 0%, #3B82F6 100%);
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
              ">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0F23" stroke-width="2">
                  <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                </svg>
              </button>
            </div>
            <div style="
              font-size: 9px;
              color: rgba(100, 200, 255, 0.4);
              text-align: center;
              margin-top: 8px;
              letter-spacing: 0.05em;
            ">Powered by AUREM AI</div>
          </div>
        </div>
      </div>

      <!-- Animations -->
      <style>
        @keyframes aurem-bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }

        #aurem-bubble:hover {
          transform: scale(1.05);
          box-shadow: 0 6px 30px rgba(212, 175, 55, 0.6);
        }

        .aurem-quick-btn:hover {
          background: rgba(212, 175, 55, 0.2);
          transform: translateY(-2px);
        }

        #aurem-messages::-webkit-scrollbar {
          width: 6px;
        }

        #aurem-messages::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 3px;
        }

        #aurem-messages::-webkit-scrollbar-thumb {
          background: rgba(212, 175, 55, 0.3);
          border-radius: 3px;
        }
      </style>
    `;

    document.body.insertAdjacentHTML('beforeend', widgetHTML);
  };

  // Initialize widget functionality
  const initWidget = () => {
    const bubble = document.getElementById('aurem-bubble');
    const chatWindow = document.getElementById('aurem-chat-window');
    const closeBtn = document.getElementById('aurem-close');
    const sendBtn = document.getElementById('aurem-send-btn');
    const input = document.getElementById('aurem-input');
    const messages = document.getElementById('aurem-messages');
    const typing = document.getElementById('aurem-typing');
    const notificationBadge = document.getElementById('aurem-notification-badge');

    // Toggle chat window
    bubble.addEventListener('click', () => {
      const isOpen = chatWindow.style.display === 'flex';
      chatWindow.style.display = isOpen ? 'none' : 'flex';
      if (!isOpen) {
        notificationBadge.style.display = 'none';
        input.focus();
      }
    });

    closeBtn.addEventListener('click', () => {
      chatWindow.style.display = 'none';
    });

    // Send message
    const sendMessage = async () => {
      const text = input.value.trim();
      if (!text) return;

      // Add user message
      addMessage(text, 'user');
      input.value = '';

      // Show typing indicator
      typing.style.display = 'flex';

      try {
        // Call AUREM API
        const response = await fetch(`${AUREM_CONFIG.apiUrl}/chat/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: text,
            business_id: AUREM_CONFIG.businessId,
            session_id: getSessionId()
          })
        });

        const data = await response.json();
        
        setTimeout(() => {
          typing.style.display = 'none';
          addMessage(data.response || 'I apologize, I encountered an issue. Please try again.', 'assistant');
        }, 800);

      } catch (error) {
        typing.style.display = 'none';
        addMessage('Connection error. Please check your internet and try again.', 'assistant');
      }
    };

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendMessage();
    });

    // Quick actions
    document.querySelectorAll('.aurem-quick-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        input.value = getQuickActionMessage(action);
        sendMessage();
      });
    });

    // Voice input (if enabled)
    if (AUREM_CONFIG.enableVoice) {
      const voiceBtn = document.getElementById('aurem-voice-btn');
      voiceBtn.addEventListener('click', () => {
        startVoiceRecognition(input);
      });
    }
  };

  // Add message to chat
  const addMessage = (text, role) => {
    const messages = document.getElementById('aurem-messages');
    const quickActions = document.getElementById('aurem-quick-actions');
    
    // Hide quick actions after first message
    if (role === 'user' && quickActions) {
      quickActions.style.display = 'none';
    }

    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `
      align-self: ${role === 'user' ? 'flex-end' : 'flex-start'};
      max-width: 85%;
    `;

    const bubble = document.createElement('div');
    bubble.style.cssText = `
      background: ${role === 'user' 
        ? 'linear-gradient(135deg, rgba(212, 175, 55, 0.2), rgba(212, 175, 55, 0.1))'
        : 'linear-gradient(135deg, rgba(100, 200, 255, 0.15), rgba(100, 200, 255, 0.05))'
      };
      border: 1px solid ${role === 'user' 
        ? 'rgba(212, 175, 55, 0.3)'
        : 'rgba(100, 200, 255, 0.2)'
      };
      border-radius: ${role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px'};
      padding: 12px 16px;
      color: ${AUREM_CONFIG.theme.textColor};
      font-size: 14px;
      line-height: 1.5;
    `;
    bubble.textContent = text;

    const timestamp = document.createElement('div');
    timestamp.style.cssText = `
      font-size: 9px;
      color: rgba(255, 255, 255, 0.3);
      margin-top: 4px;
      text-align: ${role === 'user' ? 'right' : 'left'};
      letter-spacing: 0.05em;
    `;
    timestamp.textContent = `${role === 'user' ? 'You' : 'ORA'} • ${new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;

    messageDiv.appendChild(bubble);
    messageDiv.appendChild(timestamp);
    messages.appendChild(messageDiv);
    messages.scrollTop = messages.scrollHeight;
  };

  // Helper functions
  const getSessionId = () => {
    let sessionId = localStorage.getItem('aurem_session_id');
    if (!sessionId) {
      sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      localStorage.setItem('aurem_session_id', sessionId);
    }
    return sessionId;
  };

  const getQuickActionMessage = (action) => {
    const messages = {
      book: 'I want to book a meeting',
      pricing: 'What are your pricing plans?',
      demo: 'Can I see a demo?',
      help: 'I need help with my business automation'
    };
    return messages[action] || 'Hello';
  };

  const startVoiceRecognition = (inputElement) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Voice input not supported in this browser');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
      inputElement.value = event.results[0][0].transcript;
    };

    recognition.start();
  };

  // Auto-initialize on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createWidget();
      initWidget();
    });
  } else {
    createWidget();
    initWidget();
  }

  // Expose configuration function
  window.AUREM = {
    init: (config) => {
      Object.assign(AUREM_CONFIG, config);
    },
    open: () => {
      document.getElementById('aurem-chat-window').style.display = 'flex';
    },
    close: () => {
      document.getElementById('aurem-chat-window').style.display = 'none';
    },
    sendMessage: (text) => {
      document.getElementById('aurem-input').value = text;
      document.getElementById('aurem-send-btn').click();
    }
  };

})();
