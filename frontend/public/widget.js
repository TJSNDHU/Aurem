/**
 * AUREM Embeddable Widget - FULLY AUTOMATED
 * 
 * AUTO-DETECTS customer website theme and adapts colors automatically!
 * 
 * Usage (Minimal - NO theme config needed!):
 * <script src="https://aurem.live/widget.js" 
 *         data-api-key="sk_aurem_live_xxxxx"></script>
 * 
 * Optional overrides:
 * data-position="bottom-right" (auto-detects best position)
 * data-color="#D4AF37" (manual override - otherwise auto-detects)
 */

(function() {
  'use strict';

  // Configuration from data attributes
  const scriptTag = document.currentScript;
  const manualConfig = {
    apiKey: scriptTag.getAttribute('data-api-key'),
    position: scriptTag.getAttribute('data-position'),
    color: scriptTag.getAttribute('data-color'),
    apiUrl: scriptTag.getAttribute('data-api-url') || 'https://aurem.live/api/public'
  };

  // Validate API key
  if (!manualConfig.apiKey || !manualConfig.apiKey.startsWith('sk_aurem_')) {
    console.error('[AUREM Widget] Invalid or missing API key');
    return;
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // INTELLIGENT THEME DETECTION
  // ═══════════════════════════════════════════════════════════════════════════════

  function detectWebsiteTheme() {
    const theme = {
      isDarkMode: false,
      primaryColor: '#D4AF37',
      backgroundColor: '#FFFFFF',
      textColor: '#000000',
      accentColor: '#8B7355'
    };

    try {
      // 1. Detect dark/light mode from body background
      const bodyBg = window.getComputedStyle(document.body).backgroundColor;
      const bgLightness = getColorLightness(bodyBg);
      theme.isDarkMode = bgLightness < 50;
      theme.backgroundColor = bodyBg;

      // 2. Extract primary brand color from common sources
      const primaryColor = 
        getCSSVariable('--primary-color') ||
        getCSSVariable('--brand-color') ||
        getCSSVariable('--theme-color') ||
        getCSSVariable('--accent-color') ||
        getButtonColor() ||
        getLinkColor() ||
        getHeaderColor();

      if (primaryColor) {
        theme.primaryColor = primaryColor;
      }

      // 3. Auto-generate accent color (darker shade of primary)
      theme.accentColor = adjustColorBrightness(theme.primaryColor, -20);

      // 4. Set appropriate text color based on mode
      theme.textColor = theme.isDarkMode ? '#FFFFFF' : '#000000';

      console.log('[AUREM Widget] Auto-detected theme:', theme);
      return theme;

    } catch (error) {
      console.warn('[AUREM Widget] Theme detection failed, using defaults:', error);
      return theme;
    }
  }

  function getCSSVariable(varName) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
    return value || null;
  }

  function getButtonColor() {
    const buttons = document.querySelectorAll('button, .btn, [class*="button"]');
    for (let btn of buttons) {
      const bg = window.getComputedStyle(btn).backgroundColor;
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
        return bg;
      }
    }
    return null;
  }

  function getLinkColor() {
    const links = document.querySelectorAll('a');
    for (let link of links) {
      const color = window.getComputedStyle(link).color;
      if (color && color !== 'rgb(0, 0, 238)') { // Not default blue
        return color;
      }
    }
    return null;
  }

  function getHeaderColor() {
    const headers = document.querySelectorAll('header, .header, nav, .navbar');
    for (let header of headers) {
      const bg = window.getComputedStyle(header).backgroundColor;
      if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
        return bg;
      }
    }
    return null;
  }

  function getColorLightness(color) {
    // Convert color to RGB
    const rgb = color.match(/\d+/g);
    if (!rgb) return 50;
    
    const [r, g, b] = rgb.map(Number);
    // Calculate perceived lightness
    return (0.299 * r + 0.587 * g + 0.114 * b);
  }

  function rgbToHex(rgb) {
    const match = rgb.match(/\d+/g);
    if (!match) return '#D4AF37';
    
    const [r, g, b] = match.map(Number);
    return '#' + [r, g, b].map(x => {
      const hex = x.toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    }).join('');
  }

  function adjustColorBrightness(color, percent) {
    // Convert to hex if RGB
    if (color.startsWith('rgb')) {
      color = rgbToHex(color);
    }

    const num = parseInt(color.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, Math.min(255, (num >> 16) + amt));
    const G = Math.max(0, Math.min(255, (num >> 8 & 0x00FF) + amt));
    const B = Math.max(0, Math.min(255, (num & 0x0000FF) + amt));
    
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // INTELLIGENT POSITIONING
  // ═══════════════════════════════════════════════════════════════════════════════

  function detectBestPosition() {
    // Check if bottom-right is cluttered
    const bottomRightElements = document.elementsFromPoint(
      window.innerWidth - 80,
      window.innerHeight - 80
    );

    // If there are many elements in bottom-right, try bottom-left
    if (bottomRightElements.length > 3) {
      console.log('[AUREM Widget] Bottom-right cluttered, using bottom-left');
      return 'bottom-left';
    }

    return 'bottom-right'; // Default
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // RESPONSIVE WIDTH
  // ═══════════════════════════════════════════════════════════════════════════════

  function getResponsiveWidth() {
    const screenWidth = window.innerWidth;
    
    if (screenWidth < 480) {
      return '100vw'; // Full width on mobile
    } else if (screenWidth < 768) {
      return '90vw'; // 90% on small tablets
    } else if (screenWidth < 1024) {
      return '400px'; // Fixed on tablets
    } else {
      return '420px'; // Larger on desktop
    }
  }

  function getResponsiveHeight() {
    const screenHeight = window.innerHeight;
    
    if (screenHeight < 600) {
      return '80vh';
    } else if (screenHeight < 800) {
      return '600px';
    } else {
      return '650px';
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // APPLY CONFIGURATION
  // ═══════════════════════════════════════════════════════════════════════════════

  const autoTheme = detectWebsiteTheme();
  
  const config = {
    apiKey: manualConfig.apiKey,
    position: manualConfig.position || detectBestPosition(),
    color: manualConfig.color ? manualConfig.color : rgbToHex(autoTheme.primaryColor),
    isDarkMode: autoTheme.isDarkMode,
    textColor: autoTheme.textColor,
    accentColor: autoTheme.accentColor,
    width: getResponsiveWidth(),
    height: getResponsiveHeight(),
    apiUrl: manualConfig.apiUrl
  };

  console.log('[AUREM Widget] Final config:', config);

  // ═══════════════════════════════════════════════════════════════════════════════
  // BUILD WIDGET UI
  // ═══════════════════════════════════════════════════════════════════════════════

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

  // Auto-adjust button color for contrast
  const buttonTextColor = getColorLightness(config.color) > 128 ? '#000' : '#FFF';

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
    background: linear-gradient(135deg, ${config.color} 0%, ${config.accentColor} 100%);
    border: none;
    color: ${buttonTextColor};
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

  // Chat window background adapts to site theme
  const windowBg = config.isDarkMode ? '#0A0A0A' : '#FFFFFF';
  const messageBg = config.isDarkMode ? '#1A1A1A' : '#F5F5F5';
  const inputBg = config.isDarkMode ? '#1A1A1A' : '#FAFAFA';
  const inputBorder = config.isDarkMode ? '#333' : '#E0E0E0';
  const windowTextColor = config.isDarkMode ? '#F4F4F4' : '#1A1A1A';

  // Create chat window (responsive)
  const chatWindow = document.createElement('div');
  chatWindow.id = 'aurem-chat-window';
  chatWindow.style.cssText = `
    display: none;
    width: ${config.width};
    height: ${config.height};
    max-width: 95vw;
    max-height: 90vh;
    background: ${windowBg};
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    overflow: hidden;
    flex-direction: column;
    position: fixed;
    ${config.position.includes('bottom') ? 'bottom: 90px;' : 'top: 80px;'}
    ${config.position.includes('right') ? 'right: 20px;' : 'left: 20px;'}
    transition: all 0.3s ease;
  `;

  // Chat header
  const chatHeader = document.createElement('div');
  chatHeader.style.cssText = `
    background: linear-gradient(135deg, ${config.color} 0%, ${config.accentColor} 100%);
    color: ${buttonTextColor};
    padding: 16px;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
  `;
  chatHeader.innerHTML = `
    <div>
      <div style="font-size: 16px;">AUREM AI</div>
      <div style="font-size: 11px; opacity: 0.8;">Intelligent Assistant</div>
    </div>
    <button id="aurem-close-btn" style="background: none; border: none; color: ${buttonTextColor}; cursor: pointer; font-size: 28px; line-height: 1;">&times;</button>
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
    background: ${windowBg};
  `;

  // Input container
  const inputContainer = document.createElement('div');
  inputContainer.style.cssText = `
    padding: 16px;
    border-top: 1px solid ${inputBorder};
    display: flex;
    gap: 8px;
    background: ${windowBg};
  `;
  inputContainer.innerHTML = `
    <input 
      id="aurem-input" 
      type="text" 
      placeholder="Type your message..."
      style="flex: 1; padding: 12px; background: ${inputBg}; border: 1px solid ${inputBorder}; border-radius: 8px; color: ${windowTextColor}; font-size: 14px; outline: none;"
    />
    <button 
      id="aurem-send-btn"
      style="padding: 12px 20px; background: ${config.color}; border: none; border-radius: 8px; color: ${buttonTextColor}; font-weight: 600; cursor: pointer; transition: opacity 0.2s;"
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

  // Responsive window resize
  window.addEventListener('resize', () => {
    chatWindow.style.width = getResponsiveWidth();
    chatWindow.style.height = getResponsiveHeight();
  });

  // Functions
  function toggleChat() {
    isOpen = !isOpen;
    chatWindow.style.display = isOpen ? 'flex' : 'none';
    chatButton.style.display = isOpen ? 'none' : 'flex';
    if (isOpen) input.focus();
  }

  function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    const isUser = role === 'user';
    
    messageDiv.style.cssText = `
      padding: 12px 16px;
      border-radius: 16px;
      max-width: 80%;
      ${isUser 
        ? `background: linear-gradient(135deg, ${config.color} 0%, ${config.accentColor} 100%); color: ${buttonTextColor}; align-self: flex-end; border-bottom-right-radius: 4px;` 
        : `background: ${messageBg}; color: ${windowTextColor}; align-self: flex-start; border-bottom-left-radius: 4px;`
      }
      font-size: 14px;
      line-height: 1.5;
      word-wrap: break-word;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
      padding: 12px 16px;
      background: ${messageBg};
      border-radius: 16px;
      color: ${windowTextColor};
      opacity: 0.7;
      font-size: 14px;
      align-self: flex-start;
      border-bottom-left-radius: 4px;
    `;
    typingDiv.innerHTML = '<span style="opacity: 0.6;">●</span> <span style="opacity: 0.8;">●</span> <span>●</span> AUREM is typing...';
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

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

  console.log('[AUREM Widget] Loaded successfully with auto-theme detection');
})();
