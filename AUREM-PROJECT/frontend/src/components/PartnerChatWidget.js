import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { 
  MessageCircle,
  ChevronUp,
  ChevronDown,
  Send,
  Loader2
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API = (typeof window !== 'undefined' && window.location.hostname.includes('reroots.ca') ? 'https://reroots.ca' : process.env.REACT_APP_BACKEND_URL) + '/api';

// Partner Chat Widget - Messaging between Partner/Influencer and Admin
const PartnerChatWidget = ({ partnerCode, partnerName }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const messagesEndRef = useRef(null);
  const pollIntervalRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchMessages = useCallback(async () => {
    if (!partnerCode) return;
    try {
      const res = await axios.get(`${API}/partner-chat/${partnerCode}`);
      setMessages(res.data.messages || []);
    } catch (error) {
      console.error("Error fetching messages:", error);
    }
  }, [partnerCode]);

  const fetchUnreadCount = useCallback(async () => {
    if (!partnerCode) return;
    try {
      const res = await axios.get(`${API}/partner-chat/unread-count/${partnerCode}`);
      setUnreadCount(res.data.unread_count || 0);
    } catch (error) {
      console.error("Error fetching unread count:", error);
    }
  }, [partnerCode]);

  const [adminOnline, setAdminOnline] = useState(false);

  useEffect(() => {
    if (partnerCode) {
      fetchUnreadCount();
      // Poll for new messages every 10 seconds
      pollIntervalRef.current = setInterval(fetchUnreadCount, 10000);
    }
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [partnerCode, fetchUnreadCount]);

  // Partner heartbeat - send every 30 seconds when widget is open
  useEffect(() => {
    if (partnerCode) {
      const sendHeartbeat = async () => {
        try {
          await axios.post(`${API}/presence/heartbeat`, { 
            user_type: "partner",
            partner_code: partnerCode 
          });
        } catch (e) {
          // Silently fail
        }
      };
      
      sendHeartbeat(); // Send immediately
      const heartbeatInterval = setInterval(sendHeartbeat, 30000);
      return () => clearInterval(heartbeatInterval);
    }
  }, [partnerCode]);

  // Check if admin is online
  useEffect(() => {
    if (partnerCode) {
      const checkAdminStatus = async () => {
        try {
          const res = await axios.get(`${API}/presence/status?partner_code=${partnerCode}`);
          setAdminOnline(res.data.admin_online);
        } catch (e) {
          // Silently fail
        }
      };
      
      checkAdminStatus();
      const statusInterval = setInterval(checkAdminStatus, 15000);
      return () => clearInterval(statusInterval);
    }
  }, [partnerCode]);

  useEffect(() => {
    if (isOpen && partnerCode) {
      setLoading(true);
      fetchMessages().finally(() => setLoading(false));
      // Mark messages as read
      axios.post(`${API}/partner-chat/mark-read`, { partner_code: partnerCode }).catch(console.error);
      setUnreadCount(0);
      
      // Poll for new messages when open
      const interval = setInterval(fetchMessages, 5000);
      return () => clearInterval(interval);
    }
  }, [isOpen, partnerCode, fetchMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || !partnerCode || sending) return;
    
    setSending(true);
    try {
      await axios.post(`${API}/partner-chat/send`, {
        partner_code: partnerCode,
        message: newMessage.trim()
      });
      setNewMessage("");
      fetchMessages();
      toast.success("Message sent!");
    } catch (error) {
      toast.error("Failed to send message");
    }
    setSending(false);
  };

  if (!partnerCode) return null;

  return (
    <Card className="border-[#D4AF37]/30">
      <CardHeader 
        className="cursor-pointer hover:bg-[#FAF8F5] transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <div className="relative">
              <MessageCircle className="h-5 w-5 text-[#D4AF37]" />
              {/* Admin Online Indicator */}
              <span className={`absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border-2 border-white ${
                adminOnline ? "bg-green-500 animate-pulse" : "bg-red-500"
              }`} />
            </div>
            <span>Chat with Admin</span>
            {/* Online Status Badge */}
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              adminOnline 
                ? "bg-green-100 text-green-700" 
                : "bg-gray-100 text-gray-600"
            }`}>
              {adminOnline ? "Online" : "Offline"}
            </span>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {unreadCount}
              </span>
            )}
          </CardTitle>
          {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </div>
      </CardHeader>
      
      {isOpen && (
        <CardContent className="space-y-4">
          {/* Messages Area */}
          <div className="h-64 overflow-y-auto bg-[#FAF8F5] rounded-lg p-3 space-y-3">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-[#D4AF37]" />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center text-gray-500 h-full flex flex-col items-center justify-center">
                <MessageCircle className="h-10 w-10 text-gray-300 mb-2" />
                <p>No messages yet</p>
                <p className="text-sm">Send a message to start chatting with admin</p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === "partner" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg px-3 py-2 ${
                      msg.sender === "partner"
                        ? "bg-[#D4AF37] text-white"
                        : "bg-white border border-gray-200"
                    }`}
                  >
                    <p className="text-sm">{msg.message}</p>
                    <p className={`text-xs mt-1 ${msg.sender === "partner" ? "text-white/70" : "text-gray-400"}`}>
                      {msg.sender === "admin" && <span className="font-medium">{msg.admin_name || "Admin"} • </span>}
                      {new Date(msg.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>
          
          {/* Message Input */}
          <form onSubmit={sendMessage} className="flex gap-2">
            <Input
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              placeholder="Type your message..."
              className="flex-1"
              disabled={sending}
            />
            <Button 
              type="submit" 
              disabled={!newMessage.trim() || sending}
              className="bg-[#D4AF37] hover:bg-[#B8960F] text-[#2D2A2E]"
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </form>
        </CardContent>
      )}
    </Card>
  );
};

export default PartnerChatWidget;
