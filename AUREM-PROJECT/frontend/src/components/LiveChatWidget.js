import React, { useState, useEffect, useRef, useContext, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageCircle, X, Bot, Send, Loader2, Phone } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { StoreSettingsContext } from '@/contexts';

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

const LiveChatWidget = () => {
  const { settings } = useContext(StoreSettingsContext) || {};
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false); // Defer initialization
  const [showWidget, setShowWidget] = useState(false); // NEW: Delay widget appearance for TBT optimization
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [customerName, setCustomerName] = useState("");
  const [showNameInput, setShowNameInput] = useState(true);
  const [showCallbackForm, setShowCallbackForm] = useState(false);
  const [callbackForm, setCallbackForm] = useState({ name: '', phone: '', email: '', preferred_time: '', reason: '' });
  const [submittingCallback, setSubmittingCallback] = useState(false);
  const messagesEndRef = useRef(null);

  // Hide on checkout, cart, mission-control, bio-scan, OROÉ, LA VELA, and Admin pages
  const hiddenPaths = ['/checkout', '/cart', '/mission-control', '/Bio-Age-Repair-Scan', '/quiz', '/skin-scan', '/oroe', '/ritual', '/la-vela-bianca', '/lavela', '/admin', '/new-admin', '/reroots-admin', '/app'];
  const shouldHide = hiddenPaths.some(path => location.pathname.toLowerCase().includes(path.toLowerCase()));

  const chatEnabled = settings?.live_chat?.enabled;
  const welcomeMessage = settings?.live_chat?.welcome_message || "Hi! Welcome to ReRoots. How can we help you today?";
  const aiGreeting = settings?.live_chat?.ai_greeting || "Hello! I'm your ReRoots assistant. How can I help you?";

  // TBT OPTIMIZATION: Delay chat widget appearance by 5 seconds
  // This prevents the chat widget from stealing main thread during initial page load
  useEffect(() => {
    const timer = setTimeout(() => {
      setShowWidget(true);
    }, 5000); // 5 second delay after page load
    
    // Also show immediately on user interaction (scroll/click)
    const showOnInteraction = () => {
      setShowWidget(true);
      window.removeEventListener('scroll', showOnInteraction);
      window.removeEventListener('click', showOnInteraction);
    };
    
    window.addEventListener('scroll', showOnInteraction, { passive: true, once: true });
    window.addEventListener('click', showOnInteraction, { once: true });
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('scroll', showOnInteraction);
      window.removeEventListener('click', showOnInteraction);
    };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize chat only when user clicks to open (performance optimization)
  const initializeChat = useCallback(() => {
    if (isInitialized) return;
    setIsInitialized(true);
    
    const savedConvId = localStorage.getItem("reroots_chat_conversation");
    const savedName = localStorage.getItem("reroots_chat_name");
    if (savedConvId) {
      setConversationId(savedConvId);
      setShowNameInput(false);
    }
    if (savedName) {
      setCustomerName(savedName);
      setShowNameInput(false);
    }
  }, [isInitialized]);

  // Handle opening chat - initialize on first open
  const handleOpenChat = useCallback(() => {
    initializeChat();
    setIsOpen(true);
  }, [initializeChat]);

  const startChat = () => {
    if (!customerName.trim()) {
      setCustomerName("Guest");
    }
    localStorage.setItem("reroots_chat_name", customerName || "Guest");
    setShowNameInput(false);
    // Add initial greeting
    setMessages([{ sender: "ai", content: aiGreeting, id: Date.now() }]);
  };

  const submitCallbackRequest = async () => {
    if (!callbackForm.name.trim() || !callbackForm.phone.trim()) {
      toast.error("Please provide your name and phone number");
      return;
    }
    setSubmittingCallback(true);
    try {
      await axios.post(`${API}/callback-request`, {
        customer_name: callbackForm.name,
        phone: callbackForm.phone,
        email: callbackForm.email,
        preferred_time: callbackForm.preferred_time,
        reason: callbackForm.reason
      });
      toast.success(settings?.thank_you_messages?.callback || "Callback request submitted! We'll call you soon.");
      setShowCallbackForm(false);
      setCallbackForm({ name: '', phone: '', email: '', preferred_time: '', reason: '' });
    } catch (err) {
      toast.error("Failed to submit request. Please try again.");
    }
    setSubmittingCallback(false);
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg = { sender: "customer", content: input, id: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    const messageText = input;
    setInput("");
    setLoading(true);

    try {
      const res = await axios.post(`${API}/chat/customer`, {
        message: messageText,
        conversation_id: conversationId,
        customer_name: customerName || "Guest"
      });

      setConversationId(res.data.conversation_id);
      localStorage.setItem("reroots_chat_conversation", res.data.conversation_id);

      if (res.data.response) {
        setMessages(prev => [...prev, { 
          sender: "ai", 
          content: res.data.response, 
          id: Date.now() + 1 
        }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { 
        sender: "ai", 
        content: "Sorry, something went wrong. Please try again.", 
        id: Date.now() + 1 
      }]);
    }
    setLoading(false);
  };

  // Hide on checkout/cart pages or if chat not enabled, or if widget shouldn't show yet
  if (!chatEnabled || shouldHide || !showWidget) return null;

  return (
    <div className="fixed bottom-40 right-6 z-50">
      {isOpen && (
        <div
          className="absolute bottom-16 right-0 bg-white rounded-2xl shadow-2xl w-80 sm:w-96 mb-4 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-[#F8A5B8] to-[#F8A5B8]/80 p-4 text-white">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-display font-bold">ReRoots Support</h3>
                <p className="text-xs text-white/80">We typically reply instantly</p>
              </div>
            </div>
          </div>
          
          {/* Chat Area */}
          <div className="h-72 overflow-y-auto p-4 bg-[#FDF9F9]">
            {showNameInput ? (
              <div className="flex flex-col items-center justify-center h-full space-y-4">
                <div className="w-16 h-16 bg-[#F8A5B8]/20 rounded-full flex items-center justify-center">
                  <MessageCircle className="h-8 w-8 text-[#F8A5B8]" />
                </div>
                <p className="text-center text-[#2D2A2E] font-medium">{welcomeMessage}</p>
                <Input
                  placeholder="Your name (optional)"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  className="max-w-[200px]"
                />
                <Button onClick={startChat} className="bg-[#F8A5B8] hover:bg-[#F8A5B8]/90 text-[#2D2A2E]">
                  Start Chat
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.sender === "customer" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[80%] rounded-2xl p-3 ${
                      msg.sender === "customer" 
                        ? "bg-[#2D2A2E] text-white rounded-br-md" 
                        : "bg-white text-[#2D2A2E] rounded-bl-md shadow-sm"
                    }`}>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-white rounded-2xl rounded-bl-md p-3 shadow-sm">
                      <Loader2 className="h-4 w-4 animate-spin text-[#F8A5B8]" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input Area */}
          {!showNameInput && !showCallbackForm && (
            <div className="p-3 border-t bg-white">
              <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type a message..."
                  disabled={loading}
                  className="flex-1 rounded-full"
                />
                <Button 
                  type="submit" 
                  disabled={loading || !input.trim()} 
                  size="icon"
                  className="rounded-full bg-[#F8A5B8] hover:bg-[#F8A5B8]/90"
                >
                  <Send className="h-4 w-4 text-white" />
                </Button>
              </form>
              <button
                onClick={() => setShowCallbackForm(true)}
                className="w-full mt-2 text-xs text-[#F8A5B8] hover:text-[#2D2A2E] flex items-center justify-center gap-1"
              >
                <Phone className="h-3 w-3" /> Request a callback from our team
              </button>
            </div>
          )}

          {/* Callback Request Form */}
          {showCallbackForm && (
            <div className="p-4 border-t bg-white space-y-3">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-sm flex items-center gap-2">
                  <Phone className="h-4 w-4 text-[#F8A5B8]" /> Request Callback
                </h4>
                <button onClick={() => setShowCallbackForm(false)} className="text-gray-400 hover:text-gray-600">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <Input
                placeholder="Your Name *"
                value={callbackForm.name}
                onChange={(e) => setCallbackForm({ ...callbackForm, name: e.target.value })}
                className="text-sm"
              />
              <Input
                placeholder="Phone Number *"
                value={callbackForm.phone}
                onChange={(e) => setCallbackForm({ ...callbackForm, phone: e.target.value })}
                className="text-sm"
              />
              <Input
                placeholder="Email (optional)"
                value={callbackForm.email}
                onChange={(e) => setCallbackForm({ ...callbackForm, email: e.target.value })}
                className="text-sm"
              />
              <select
                value={callbackForm.preferred_time}
                onChange={(e) => setCallbackForm({ ...callbackForm, preferred_time: e.target.value })}
                className="w-full text-sm border rounded-md px-3 py-2"
              >
                <option value="">Preferred time (optional)</option>
                <option value="morning">Morning (9am - 12pm)</option>
                <option value="afternoon">Afternoon (12pm - 5pm)</option>
                <option value="evening">Evening (5pm - 8pm)</option>
              </select>
              <Input
                placeholder="What would you like to discuss?"
                value={callbackForm.reason}
                onChange={(e) => setCallbackForm({ ...callbackForm, reason: e.target.value })}
                className="text-sm"
              />
              <Button
                onClick={submitCallbackRequest}
                disabled={submittingCallback}
                className="w-full bg-[#F8A5B8] hover:bg-[#F8A5B8]/90 text-white"
              >
                {submittingCallback ? "Submitting..." : "Request Callback"}
              </Button>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => isOpen ? setIsOpen(false) : handleOpenChat()}
        className={`w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all ${
          isOpen ? "bg-[#2D2A2E] rotate-90" : "bg-[#F8A5B8] hover:scale-110"
        }`}
        data-testid="live-chat-toggle"
        aria-label={isOpen ? "Close live chat" : "Open live chat"}
      >
        {isOpen ? (
          <X className="h-6 w-6 text-white" aria-hidden="true" />
        ) : (
          <MessageCircle className="h-6 w-6 text-white" aria-hidden="true" />
        )}
      </button>
    </div>
  );
};

export default LiveChatWidget;
