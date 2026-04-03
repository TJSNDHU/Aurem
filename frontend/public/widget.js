/**
 * AUREM Embeddable Widget
 * 
 * Usage:
 * <script src="https://aurem.live/widget.js" 
 *         data-api-key="sk_aurem_live_xxxxx"
 *         data-position="bottom-right"
 *         data-color="#D4AF37"></script>
 */

(function() {
  'use strict';

  // Configuration from data attributes
  const scriptTag = document.currentScript;
  const config = {
    apiKey: scriptTag.getAttribute('data-api-key'),
    position: scriptTag.getAttribute('data-position') || 'bottom-right',
    color: scriptTag.getAttribute('data-color') || '#D4AF37',
    apiUrl: scriptTag.getAttribute('data-api-url') || 'https://aurem.live/api/v1'
  };

  // Validate API key
  if (!config.apiKey || !config.apiKey.startsWith('sk_aurem_')) {
    console.error('[AUREM Widget] Invalid or missing API key');
    return;
  }

  // State
  let isOpen = false;
  let conversationId = null;
  let messages = [];

  // Create widget container
  const widgetContainer = document.createElement('div');
  widgetContainer.id = 'aurem-widget-container';
  widgetContainer.style.cssText = `
    position: fixed;
    ${config.position.includes('bottom') ? 'bottom: 20px;' : 'top: 20px;'}
    ${config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
    z-index: 999999;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  `;

  // Create chat button
  const chatButton = document.createElement('button');
  chatButton.id = 'aurem-chat-button';
  chatButton.innerHTML = `
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
    </svg>
  `;
  chatButton.style.cssText = `
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, ${config.color} 0%, ${adjustColor(config.color, -20)} 100%);
    border: none;
    color: #000;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s, box-shadow 0.2s;
  `;
  
  chatButton.onmouseover = () => {
    chatButton.style.transform = 'scale(1.1)';
    chatButton.style.boxShadow = '0 6px 16px rgba(0,0,0,0.4)';
  };
  chatButton.onmouseout = () => {
    chatButton.style.transform = 'scale(1)';
    chatButton.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
  };

  // Create chat window
  const chatWindow = document.createElement('div');
  chatWindow.id = 'aurem-chat-window';
  chatWindow.style.cssText = `
    display: none;
    width: 380px;
    height: 600px;
    max-width: 90vw;
    max-height: 80vh;
    background: #0A0A0A;
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    overflow: hidden;
    flex-direction: column;
    position: absolute;
    ${config.position.includes('bottom') ? 'bottom: 80px;' : 'top: 0;'}
    ${config.position.includes('right') ? 'right: 0;' : 'left: 0;'}
  `;

  // Chat header
  const chatHeader = document.createElement('div');
  chatHeader.style.cssText = `
    background: linear-gradient(135deg, ${config.color} 0%, ${adjustColor(config.color, -20)} 100%);
    color: #000;
    padding: 16px;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
  `;
  chatHeader.innerHTML = `
    <div>
      <div style="font-size: 16px;">AUREM AI</div>
      <div style="font-size: 11px; opacity: 0.8;">Powered by AI</div>
    </div>
    <button id="aurem-close-btn" style="background: none; border: none; color: #000; cursor: pointer; font-size: 24px;">&times;</button>
  `;

  // Messages container
  const messagesContainer = document.createElement('div');
  messagesContainer.id = 'aurem-messages';
  messagesContainer.style.cssText = `
    flex: 1;
    padding: 16px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  `;

  // Input container
  const inputContainer = document.createElement('div');
  inputContainer.style.cssText = `
    padding: 16px;
    border-top: 1px solid #1A1A1A;
    display: flex;
    gap: 8px;
  `;
  inputContainer.innerHTML = `
    <input 
      id="aurem-input" 
      type="text" 
      placeholder="Type your message..."
      style="flex: 1; padding: 12px; background: #1A1A1A; border: 1px solid #333; border-radius: 8px; color: #F4F4F4; font-size: 14px; outline: none;"
    />
    <button 
      id="aurem-send-btn"
      style="padding: 12px 20px; background: ${config.color}; border: none; border-radius: 8px; color: #000; font-weight: 600; cursor: pointer;"
    >Send</button>
  `;

  // Assemble chat window
  chatWindow.appendChild(chatHeader);
  chatWindow.appendChild(messagesContainer);
  chatWindow.appendChild(inputContainer);

  // Assemble widget
  widgetContainer.appendChild(chatButton);
  widgetContainer.appendChild(chatWindow);
  document.body.appendChild(widgetContainer);

  // Show welcome message
  addMessage('assistant', 'Hello! I\'m AUREM AI. How can I help you today?');

  // Event listeners
  chatButton.onclick = toggleChat;
  document.getElementById('aurem-close-btn').onclick = toggleChat;
  
  const input = document.getElementById('aurem-input');
  const sendBtn = document.getElementById('aurem-send-btn');
  
  sendBtn.onclick = sendMessage;
  input.onkeypress = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  // Functions
  function toggleChat() {
    isOpen = !isOpen;
    chatWindow.style.display = isOpen ? 'flex' : 'none';
    chatButton.style.display = isOpen ? 'none' : 'flex';
    if (isOpen) input.focus();
  }

  function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `
      padding: 12px;
      border-radius: 12px;
      max-width: 80%;
      ${role === 'user' 
        ? `background: ${config.color}; color: #000; align-self: flex-end;` 
        : 'background: #1A1A1A; color: #F4F4F4; align-self: flex-start;'
      }
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
    `;
    messageDiv.textContent = content;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    messages.push({ role, content });
  }

  async function sendMessage() {
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    addMessage('user', message);

    // Show typing indicator
    const typingDiv = document.createElement('div');
    typingDiv.id = 'aurem-typing';
    typingDiv.style.cssText = `
      padding: 12px;
      background: #1A1A1A;
      border-radius: 12px;
      color: #888;
      font-size: 14px;
      align-self: flex-start;
    `;
    typingDiv.textContent = 'AUREM is typing...';
    messagesContainer.appendChild(typingDiv);

    try {
      const response = await fetch(`${config.apiUrl}/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${config.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: message,
          conversation_id: conversationId
        })
      });

      // Remove typing indicator
      typingDiv.remove();

      if (response.ok) {
        const data = await response.json();
        conversationId = data.conversation_id;
        addMessage('assistant', data.response);
      } else {
        addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
      }
    } catch (error) {
      typingDiv.remove();
      addMessage('assistant', 'Connection error. Please check your internet and try again.');
      console.error('[AUREM Widget] Error:', error);
    }
  }

  function adjustColor(color, percent) {
    const num = parseInt(color.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = (num >> 16) + amt;
    const G = (num >> 8 & 0x00FF) + amt;
    const B = (num & 0x0000FF) + amt;
    return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
      (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
      (B < 255 ? B < 1 ? 0 : B : 255))
      .toString(16).slice(1);
  }

  console.log('[AUREM Widget] Loaded successfully');
})();
