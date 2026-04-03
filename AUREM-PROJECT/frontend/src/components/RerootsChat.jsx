/**
 * RerootsChat - Embeddable Chat Widget for Reroots AI
 * ═══════════════════════════════════════════════════════════════════
 * Intercom/Drift-style chat widget with brand isolation and security.
 * 
 * THEMES:
 * theme="light" → Website (cream/ivory backgrounds)
 * theme="dark"  → Mobile app (obsidian black backgrounds)
 * 
 * MOBILE:
 * Detects mobile viewport and switches to full-screen mode
 * 
 * © 2025 Reroots Aesthetics Inc. All rights reserved.
 * Reroots AI™ is a proprietary AI system.
 * ═══════════════════════════════════════════════════════════════════
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MessageCircle, X, Send, Loader2, AlertCircle, Camera, Image as ImageIcon, Globe } from 'lucide-react';

const API_URL = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca')) ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL;

// Language options with flags
const LANGUAGE_OPTIONS = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'fr', name: 'Français', flag: '🇫🇷' },
  { code: 'ar', name: 'العربية', flag: '🇸🇦', rtl: true },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'hi', name: 'हिन्दी', flag: '🇮🇳' },
  { code: 'zh', name: '中文', flag: '🇨🇳' },
  { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
  { code: 'pt', name: 'Português', flag: '🇧🇷' },
  { code: 'ja', name: '日本語', flag: '🇯🇵' },
  { code: 'ko', name: '한국어', flag: '🇰🇷' },
  { code: 'pa', name: 'ਪੰਜਾਬੀ', flag: '🇮🇳' },
  { code: 'ur', name: 'اردو', flag: '🇵🇰', rtl: true },
];
const BRAND_KEY = 'reroots';
const MAX_IMAGE_SIZE = 15 * 1024 * 1024; // 15MB - increased for camera photos

// Theme configurations
const THEMES = {
  light: {
    bg: '#FFFFFF',
    bgSecondary: '#F9FAFB',
    text: '#1F2937',
    textSecondary: '#6B7280',
    border: '#E5E7EB',
    userBubble: '#C8A96A',
    userText: '#FFFFFF',
    aiBubble: '#FFFFFF',
    aiText: '#1F2937',
    inputBg: '#FFFFFF',
  },
  dark: {
    bg: '#0D0D1A',
    bgSecondary: '#16162A',
    text: '#F9FAFB',
    textSecondary: '#9CA3AF',
    border: '#2D2D44',
    userBubble: '#C8A96A',
    userText: '#0D0D1A',
    aiBubble: '#1E1E36',
    aiText: '#F9FAFB',
    inputBg: '#16162A',
  }
};

// Brand configuration
const BRAND_CONFIG = {
  aiName: 'Reroots AI',
  primaryColor: '#C8A96A',
  logoPath: '/logo.png',
  poweredByText: 'Reroots Aesthetics Inc. · Powered by Reroots AI™',
  copyrightFooter: '© 2025 Reroots Aesthetics Inc. All rights reserved.\nReroots AI™ is a proprietary AI system. Unauthorized use, copying, or reproduction is prohibited.'
};

export default function RerootsChat({ theme = 'light', authToken = null, userEmail = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [remainingMessages, setRemainingMessages] = useState(20);
  const [error, setError] = useState(null);
  const [rateLimited, setRateLimited] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isAnalyzingImage, setIsAnalyzingImage] = useState(false);
  // Multilingual support - RTL detection
  const [isRTL, setIsRTL] = useState(false);
  const [detectedLanguage, setDetectedLanguage] = useState('en');
  const [showLanguageSelector, setShowLanguageSelector] = useState(false);
  const [manualLanguage, setManualLanguage] = useState(null);
  // Cross-device memory
  const [crossDeviceEnabled, setCrossDeviceEnabled] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  // Helper to get auth headers for cross-device memory
  const getAuthHeaders = () => {
    const headers = {
      'Content-Type': 'application/json',
      'X-Brand-Key': BRAND_KEY
    };
    // Check for token prop or localStorage
    const token = authToken || localStorage.getItem('token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  // Load manual language override from localStorage
  useEffect(() => {
    const savedLang = localStorage.getItem('reroots_manual_language');
    if (savedLang) {
      const langOption = LANGUAGE_OPTIONS.find(l => l.code === savedLang);
      if (langOption) {
        setManualLanguage(langOption);
        setDetectedLanguage(savedLang);
        setIsRTL(langOption.rtl || false);
      }
    }
  }, []);

  // Handle manual language selection
  const selectLanguage = async (langOption) => {
    setManualLanguage(langOption);
    setDetectedLanguage(langOption.code);
    setIsRTL(langOption.rtl || false);
    setShowLanguageSelector(false);
    
    // Save to localStorage
    localStorage.setItem('reroots_manual_language', langOption.code);
    
    // Save to MongoDB profile if session exists
    if (sessionId) {
      try {
        await fetch(`${API_URL}/api/chat-widget/set-language`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Brand-Key': BRAND_KEY
          },
          body: JSON.stringify({
            session_id: sessionId,
            language_code: langOption.code,
            language_name: langOption.name,
            is_manual_override: true
          })
        });
      } catch (err) {
        console.log('[RerootsChat] Failed to save language preference:', err);
      }
    }
  };

  // RTL Languages list
  const RTL_LANGUAGES = ['ar', 'he', 'fa', 'ur', 'yi', 'ps', 'sd'];

  // Theme colors
  const T = THEMES[theme] || THEMES.light;

  // Detect mobile viewport
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Initialize session when chat opens
  useEffect(() => {
    if (isOpen && !sessionId) {
      initializeSession();
    }
  }, [isOpen, sessionId]);

  // Detect language from user input for RTL support
  const detectLanguageFromInput = useCallback(async (text) => {
    if (!text || text.length < 5) return;
    
    try {
      const response = await fetch(`${API_URL}/api/chat-widget/detect-language`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Brand-Key': BRAND_KEY
        },
        body: JSON.stringify({ text })
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.detected && data.confidence > 0.7) {
          setDetectedLanguage(data.language_code);
          setIsRTL(data.is_rtl || RTL_LANGUAGES.includes(data.language_code));
        }
      }
    } catch (err) {
      console.log('[RerootsChat] Language detection failed:', err);
    }
  }, []);

  // Request browser geolocation after session is created
  const requestBrowserLocation = useCallback(async (sid) => {
    if (!navigator.geolocation) return;
    
    try {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const { latitude, longitude } = position.coords;
          
          // Send to backend
          try {
            await fetch(`${API_URL}/api/chat-widget/location`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-Brand-Key': BRAND_KEY
              },
              body: JSON.stringify({
                session_id: sid,
                lat: latitude,
                lon: longitude
              })
            });
            console.log('[RerootsChat] Location shared for personalized recommendations');
          } catch (err) {
            console.log('[RerootsChat] Could not share location:', err);
          }
        },
        (error) => {
          // User denied or error - that's okay, we fall back to IP detection
          console.log('[RerootsChat] Location not available:', error.message);
        },
        {
          enableHighAccuracy: false,
          timeout: 5000,
          maximumAge: 300000 // 5 minutes
        }
      );
    } catch (err) {
      console.log('[RerootsChat] Geolocation error:', err);
    }
  }, []);

  const initializeSession = async () => {
    try {
      setError(null);
      const response = await fetch(`${API_URL}/api/chat-widget/session`, {
        method: 'POST',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to start chat session');
      }

      const data = await response.json();
      setSessionId(data.session_id);

      // Request browser location for personalized weather-based recommendations
      // This runs silently in the background - if user denies, we fall back to IP detection
      requestBrowserLocation(data.session_id);

      // Link session to account for cross-device memory if user is logged in
      const token = authToken || localStorage.getItem('token');
      let previousMessages = [];
      let loadedUserName = null;
      
      if (token) {
        try {
          // Link session to account
          const linkResponse = await fetch(`${API_URL}/api/chat-widget/link-account`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ session_id: data.session_id })
          });
          
          if (linkResponse.ok) {
            const linkData = await linkResponse.json();
            setCrossDeviceEnabled(linkData.cross_device_memory_enabled);
            console.log('[RerootsChat] Cross-device memory enabled');
          }
          
          // Fetch previous conversation history for cross-device sync
          const historyResponse = await fetch(`${API_URL}/api/chat-widget/cross-device-history?limit=10`, {
            method: 'GET',
            headers: getAuthHeaders()
          });
          
          if (historyResponse.ok) {
            const historyData = await historyResponse.json();
            if (historyData.success && historyData.messages && historyData.messages.length > 0) {
              previousMessages = historyData.messages;
              loadedUserName = historyData.user_name;
              console.log(`[RerootsChat] Loaded ${previousMessages.length} previous messages`);
            }
          }
        } catch (err) {
          console.log('[RerootsChat] Could not load cross-device data:', err);
        }
      }

      // Build initial messages array
      const initialMessages = [];
      
      // Add previous conversation with divider if exists
      if (previousMessages.length > 0) {
        // Add divider marker
        initialMessages.push({
          role: 'divider',
          content: 'Previous conversation'
        });
        
        // Add previous messages
        previousMessages.forEach(msg => {
          initialMessages.push({
            role: msg.role,
            content: msg.content,
            timestamp: msg.timestamp,
            isPrevious: true
          });
        });
        
        // Add continuation divider
        initialMessages.push({
          role: 'divider',
          content: 'Continue your conversation'
        });
      }
      
      // Add welcome message
      const displayName = loadedUserName || (userEmail ? userEmail.split('@')[0] : null);
      const welcomeGreeting = displayName 
        ? `Welcome back, ${displayName}! I'm ${BRAND_CONFIG.aiName}, your skincare advisor.`
        : `Hi! I'm ${BRAND_CONFIG.aiName}, your skincare advisor.`;
      
      initialMessages.push({
        role: 'assistant',
        content: `${welcomeGreeting} How can I help you today?\n\n📷 Tip: You can share a photo of your skin and I'll analyze it to recommend the best products for you!`
      });
      
      setMessages(initialMessages);
    } catch (err) {
      console.error('Session init error:', err);
      setError('Unable to start chat. Please try again.');
    }
  };

  // ═══════════════════════════════════════════════════════════════
  // IMAGE HANDLING - Skin Analysis Feature
  // ═══════════════════════════════════════════════════════════════

  // Compress image to reduce size for upload
  const compressImage = (file, maxWidth = 1200, quality = 0.8) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          let width = img.width;
          let height = img.height;
          
          // Scale down if needed
          if (width > maxWidth) {
            height = (height * maxWidth) / width;
            width = maxWidth;
          }
          
          canvas.width = width;
          canvas.height = height;
          
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);
          
          // Convert to blob
          canvas.toBlob((blob) => {
            if (blob) {
              const compressedFile = new File([blob], file.name, {
                type: 'image/jpeg',
                lastModified: Date.now()
              });
              resolve(compressedFile);
            } else {
              reject(new Error('Compression failed'));
            }
          }, 'image/jpeg', quality);
        };
        img.onerror = reject;
        img.src = e.target.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  };

  const handleImageSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please select an image file (JPEG, PNG, WebP)');
      return;
    }

    // Validate file size - if too large, compress it
    let processedFile = file;
    if (file.size > MAX_IMAGE_SIZE) {
      setError('Image too large. Please select an image under 15MB');
      return;
    }
    
    // Compress if larger than 2MB for faster upload
    if (file.size > 2 * 1024 * 1024) {
      try {
        setError('Compressing image...');
        processedFile = await compressImage(file, 1200, 0.85);
        setError(null);
      } catch (err) {
        console.error('Compression failed:', err);
        // Continue with original file
      }
    }

    setSelectedImage(processedFile);
    setError(null);

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setImagePreview(e.target.result);
    };
    reader.readAsDataURL(processedFile);
  };

  const clearImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendImageMessage = async () => {
    if (!selectedImage || isLoading || !sessionId || rateLimited) return;

    setIsAnalyzingImage(true);
    setIsLoading(true);
    setError(null);

    // Add user message with image preview
    const userImageMessage = {
      role: 'user',
      content: inputValue.trim() || 'Can you analyze my skin from this photo?',
      image: imagePreview
    };
    setMessages(prev => [...prev, userImageMessage]);
    
    const messageText = inputValue.trim();
    setInputValue('');

    try {
      // Convert image to base64
      const reader = new FileReader();
      reader.readAsDataURL(selectedImage);
      
      reader.onload = async () => {
        const base64Image = reader.result;
        
        try {
          const response = await fetch(`${API_URL}/api/chat-widget/analyze-skin`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
              session_id: sessionId,
              message: messageText || 'Please analyze my skin from this photo and recommend products',
              image: base64Image
            })
          });

          if (!response.ok) {
            if (response.status === 429) {
              setRateLimited(true);
              throw new Error('Rate limit reached. Please try again later.');
            }
            throw new Error('Failed to analyze image');
          }

          const data = await response.json();

          if (data.success) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: data.response
            }]);
            if (data.remaining_messages !== undefined) {
              setRemainingMessages(data.remaining_messages);
            }
          } else {
            throw new Error(data.error || 'Analysis failed');
          }
        } catch (err) {
          console.error('Image analysis error:', err);
          setError(err.message || 'Unable to analyze image. Please try again.');
        } finally {
          setIsLoading(false);
          setIsAnalyzingImage(false);
          clearImage();
        }
      };

      reader.onerror = () => {
        setError('Failed to read image. Please try again.');
        setIsLoading(false);
        setIsAnalyzingImage(false);
        clearImage();
      };
    } catch (err) {
      console.error('Image processing error:', err);
      setError('Failed to process image. Please try again.');
      setIsLoading(false);
      setIsAnalyzingImage(false);
      clearImage();
    }
  };

  const sendMessage = async () => {
    // If there's an image, send image message instead
    if (selectedImage) {
      return sendImageMessage();
    }

    if (!inputValue.trim() || isLoading || !sessionId || rateLimited) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setError(null);

    // Detect language from user message for RTL support
    detectLanguageFromInput(userMessage);

    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);

    try {
      const response = await fetch(`${API_URL}/api/chat-widget/message`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage
        })
      });

      const data = await response.json();

      if (!data.success) {
        if (data.error === 'rate_limited') {
          setRateLimited(true);
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: data.message || 'Please try again later or contact us directly.',
            isError: true
          }]);
        } else {
          throw new Error(data.error || 'Failed to send message');
        }
      } else {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.response
        }]);
        setRemainingMessages(data.remaining_messages);
        
        // Update cross-device memory status
        if (data.cross_device_memory !== undefined) {
          setCrossDeviceEnabled(data.cross_device_memory);
        }
      }
    } catch (err) {
      console.error('Send message error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        isError: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const toggleChat = () => {
    setIsOpen(!isOpen);
  };

  // Mobile full-screen or desktop widget styles
  const chatWindowStyles = isMobile && isOpen
    ? 'fixed inset-0 z-50'  // Full screen on mobile
    : 'fixed bottom-24 right-6 z-50 w-[380px] max-w-[calc(100vw-48px)] h-[550px] max-h-[calc(100vh-120px)] rounded-2xl shadow-2xl';

  return (
    <>
      {/* Chat Toggle Button - hidden when full-screen mobile */}
      {!(isMobile && isOpen) && (
        <button
          onClick={toggleChat}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all duration-300 hover:scale-110"
          style={{ backgroundColor: BRAND_CONFIG.primaryColor }}
          aria-label={isOpen ? 'Close chat' : 'Open chat'}
          data-testid="chat-toggle-btn"
        >
          {isOpen ? (
            <X className="w-6 h-6 text-white" />
          ) : (
            <MessageCircle className="w-6 h-6 text-white" />
          )}
        </button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div
          className={`${chatWindowStyles} flex flex-col overflow-hidden`}
          style={{ 
            backgroundColor: T.bg,
            borderColor: T.border,
            borderWidth: isMobile ? '0' : '1px',
            borderRadius: isMobile ? '0' : '1rem'
          }}
          data-testid="chat-window"
        >
          {/* Header */}
          <div
            className="px-4 py-3 flex items-center gap-3 border-b relative"
            style={{ 
              backgroundColor: BRAND_CONFIG.primaryColor,
              borderColor: T.border
            }}
          >
            <img
              src={BRAND_CONFIG.logoPath}
              alt="Logo"
              className="w-10 h-10 rounded-full bg-white p-1 object-contain"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
            <div className="flex-1">
              <h3 className="text-white font-semibold text-lg">{BRAND_CONFIG.aiName}</h3>
              <p className="text-white/80 text-xs">Skincare Advisor</p>
            </div>
            
            {/* Language Selector */}
            <div className="relative">
              <button
                onClick={() => setShowLanguageSelector(!showLanguageSelector)}
                className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                aria-label="Select language"
                data-testid="language-selector-btn"
              >
                <span className="text-lg">{manualLanguage?.flag || '🌐'}</span>
                <Globe className="w-4 h-4 text-white" />
              </button>
              
              {/* Language Dropdown */}
              {showLanguageSelector && (
                <div 
                  className="absolute right-0 top-full mt-2 w-48 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden z-50"
                  data-testid="language-dropdown"
                >
                  <div className="p-2 border-b border-gray-100 bg-gray-50">
                    <p className="text-xs text-gray-500 font-medium">Select Language</p>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {LANGUAGE_OPTIONS.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => selectLanguage(lang)}
                        className={`w-full px-3 py-2 flex items-center gap-3 hover:bg-gray-100 transition-colors ${
                          detectedLanguage === lang.code ? 'bg-amber-50' : ''
                        }`}
                        data-testid={`lang-option-${lang.code}`}
                      >
                        <span className="text-xl">{lang.flag}</span>
                        <span className="text-sm text-gray-800">{lang.name}</span>
                        {detectedLanguage === lang.code && (
                          <span className="ml-auto text-amber-500 text-xs">✓</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            <button
              onClick={toggleChat}
              className="text-white/80 hover:text-white transition-colors"
              aria-label="Close chat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Area */}
          <div 
            className="flex-1 overflow-y-auto p-4 space-y-4"
            style={{ backgroundColor: T.bgSecondary }}
          >
            {error && (
              <div 
                className="p-3 rounded-lg text-sm flex items-center gap-2"
                style={{ 
                  backgroundColor: theme === 'dark' ? '#3B1A1A' : '#FEF2F2',
                  color: theme === 'dark' ? '#FCA5A5' : '#DC2626'
                }}
              >
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}

            {messages.map((message, index) => (
              // Handle divider messages
              message.role === 'divider' ? (
                <div key={index} className="flex items-center gap-3 py-2">
                  <div className="flex-1 h-px" style={{ backgroundColor: T.border }} />
                  <span 
                    className="text-xs font-medium px-2"
                    style={{ color: T.textSecondary }}
                  >
                    {message.content}
                  </span>
                  <div className="flex-1 h-px" style={{ backgroundColor: T.border }} />
                </div>
              ) : (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                dir={isRTL ? 'rtl' : 'ltr'}
              >
                <div
                  className={`max-w-[80%] p-3 rounded-2xl ${message.isPrevious ? 'opacity-80' : ''}`}
                  style={{
                    backgroundColor: message.role === 'user' ? T.userBubble : T.aiBubble,
                    color: message.role === 'user' ? T.userText : T.aiText,
                    borderWidth: message.role === 'user' ? '0' : '1px',
                    borderColor: T.border,
                    borderRadius: message.role === 'user' 
                      ? (isRTL ? '1rem 1rem 1rem 0.25rem' : '1rem 1rem 0.25rem 1rem')
                      : (isRTL ? '1rem 1rem 0.25rem 1rem' : '1rem 1rem 1rem 0.25rem'),
                    textAlign: isRTL ? 'right' : 'left'
                  }}
                >
                  {/* Show image if present */}
                  {message.image && (
                    <div className="mb-2">
                      <img 
                        src={message.image} 
                        alt="Uploaded skin photo" 
                        className="rounded-lg max-w-full max-h-48 object-cover"
                      />
                    </div>
                  )}
                  <p className="text-sm whitespace-pre-wrap" dir={isRTL ? 'rtl' : 'ltr'}>{message.content}</p>
                </div>
              </div>
              )
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div 
                  className="p-3 rounded-2xl"
                  style={{ 
                    backgroundColor: T.aiBubble,
                    borderWidth: '1px',
                    borderColor: T.border,
                    borderRadius: '1rem 1rem 1rem 0.25rem'
                  }}
                >
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" style={{ color: BRAND_CONFIG.primaryColor }} />
                    {isAnalyzingImage && (
                      <span className="text-xs" style={{ color: T.textSecondary }}>
                        Analyzing your skin...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Rate Limit Warning */}
          {remainingMessages <= 5 && !rateLimited && (
            <div 
              className="px-4 py-2 text-xs text-center"
              style={{ 
                backgroundColor: theme === 'dark' ? '#3D2A00' : '#FFFBEB',
                color: theme === 'dark' ? '#FCD34D' : '#B45309'
              }}
            >
              {remainingMessages} messages remaining this hour
            </div>
          )}

          {/* Input Area */}
          <div 
            className="p-4 border-t"
            style={{ 
              backgroundColor: T.bg,
              borderColor: T.border
            }}
          >
            {/* Image Preview */}
            {imagePreview && (
              <div className="mb-3 relative inline-block">
                <img 
                  src={imagePreview} 
                  alt="Preview" 
                  className="h-20 w-20 object-cover rounded-lg border-2"
                  style={{ borderColor: BRAND_CONFIG.primaryColor }}
                />
                <button
                  onClick={clearImage}
                  className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs hover:bg-red-600"
                  aria-label="Remove image"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            )}
            
            <div className="flex gap-2">
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
                data-testid="image-upload-input"
              />
              
              {/* Camera/Image button */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading || rateLimited || !sessionId}
                className="w-10 h-10 rounded-full flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                style={{ 
                  backgroundColor: T.bgSecondary,
                  borderWidth: '1px',
                  borderColor: T.border
                }}
                title="Upload skin photo for analysis"
                data-testid="image-upload-btn"
              >
                <Camera className="w-4 h-4" style={{ color: BRAND_CONFIG.primaryColor }} />
              </button>
              
              <input
                ref={inputRef}
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={rateLimited ? 'Rate limit reached' : selectedImage ? 'Add a message about your skin...' : 'Type your message...'}
                disabled={isLoading || rateLimited || !sessionId}
                dir={isRTL ? 'rtl' : 'ltr'}
                className="flex-1 px-4 py-2 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-opacity-50 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ 
                  backgroundColor: T.inputBg,
                  color: T.text,
                  borderWidth: '1px',
                  borderColor: T.border,
                  '--tw-ring-color': BRAND_CONFIG.primaryColor,
                  textAlign: isRTL ? 'right' : 'left'
                }}
                data-testid="chat-input"
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || (!inputValue.trim() && !selectedImage) || rateLimited || !sessionId}
                className="w-10 h-10 rounded-full flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                style={{ backgroundColor: BRAND_CONFIG.primaryColor }}
                data-testid="chat-send-btn"
              >
                <Send className="w-4 h-4 text-white" />
              </button>
            </div>
          </div>

          {/* Footer */}
          <div 
            className="px-4 py-2 border-t"
            style={{ 
              backgroundColor: T.bgSecondary,
              borderColor: T.border
            }}
          >
            <p 
              className="text-[10px] text-center leading-tight"
              style={{ color: T.textSecondary }}
            >
              {BRAND_CONFIG.poweredByText}
            </p>
            <p 
              className="text-[9px] text-center mt-1 whitespace-pre-line"
              style={{ color: theme === 'dark' ? '#4B5563' : '#D1D5DB' }}
            >
              {BRAND_CONFIG.copyrightFooter}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
