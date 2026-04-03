import { useState, useEffect, useCallback, useRef } from "react";
import { 
  Inbox, Mail, MessageCircle, Globe, Phone, 
  Check, X, Archive, RefreshCw, Brain, 
  ChevronRight, Clock, User, Zap, Filter,
  CheckCircle, XCircle, AlertCircle, MoreHorizontal
} from "lucide-react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

const CHANNEL_CONFIG = {
  gmail: { icon: Mail, color: "#ea4335", label: "Gmail" },
  whatsapp: { icon: MessageCircle, color: "#25D366", label: "WhatsApp" },
  web_chat: { icon: Globe, color: "#60a5fa", label: "Web Chat" },
  sms: { icon: Phone, color: "#a855f7", label: "SMS" }
};

const STATUS_CONFIG = {
  new: { color: "#60a5fa", label: "New", icon: AlertCircle },
  pending: { color: "#f59e0b", label: "Pending", icon: Clock },
  suggested: { color: GOLD, label: "Suggestion Ready", icon: Brain },
  approved: { color: "#4ade80", label: "Approved", icon: Check },
  actioned: { color: "#22d3ee", label: "Actioned", icon: CheckCircle },
  rejected: { color: "#6b7280", label: "Rejected", icon: XCircle },
  archived: { color: "#374151", label: "Archived", icon: Archive }
};

const INTENT_LABELS = {
  chat: "Reply",
  book_appointment: "Book Meeting",
  check_availability: "Check Calendar",
  send_email: "Send Email",
  send_whatsapp: "Send WhatsApp",
  create_invoice: "Create Invoice",
  create_payment: "Create Payment"
};

function MessageCard({ message, isSelected, onSelect, onApprove, onReject, onArchive }) {
  const channel = CHANNEL_CONFIG[message.channel] || CHANNEL_CONFIG.web_chat;
  const status = STATUS_CONFIG[message.status] || STATUS_CONFIG.new;
  const ChannelIcon = channel.icon;
  const StatusIcon = status.icon;
  
  const suggestion = message.brain_suggestion;
  const hasSuggestion = suggestion && suggestion.suggested_action;
  
  const senderName = message.sender?.name || message.sender?.email || message.sender?.phone || "Unknown";
  const preview = message.content?.body || message.content?.text || "";
  const subject = message.content?.subject;
  
  const receivedAt = new Date(message.received_at);
  const timeAgo = getTimeAgo(receivedAt);
  
  return (
    <div
      onClick={onSelect}
      data-testid={`inbox-message-${message.message_id}`}
      style={{
        padding: 16,
        background: isSelected ? `${GOLD}10` : OB3,
        border: `1px solid ${isSelected ? GOLD : 'rgba(201,168,76,.1)'}`,
        borderRadius: 10,
        cursor: "pointer",
        transition: "all 0.15s ease",
        marginBottom: 8
      }}
    >
      {/* Header Row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        {/* Channel Badge */}
        <div style={{
          width: 32, height: 32,
          borderRadius: 8,
          background: `${channel.color}20`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <ChannelIcon size={16} color={channel.color} />
        </div>
        
        {/* Sender & Time */}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: WH2, fontSize: 14, fontWeight: 500 }}>{senderName}</span>
            <span style={{ color: MU, fontSize: 10 }}>{timeAgo}</span>
          </div>
          {subject && (
            <div style={{ fontSize: 12, color: SV, marginTop: 2 }}>
              {subject.substring(0, 50)}{subject.length > 50 ? "..." : ""}
            </div>
          )}
        </div>
        
        {/* Status Badge */}
        <div style={{
          padding: "4px 10px",
          borderRadius: 12,
          background: `${status.color}20`,
          display: "flex",
          alignItems: "center",
          gap: 4
        }}>
          <StatusIcon size={12} color={status.color} />
          <span style={{ fontSize: 10, color: status.color, fontWeight: 500 }}>
            {status.label}
          </span>
        </div>
      </div>
      
      {/* Preview */}
      <div style={{ 
        fontSize: 13, 
        color: SV, 
        lineHeight: 1.5,
        marginBottom: hasSuggestion ? 12 : 0,
        display: "-webkit-box",
        WebkitLineClamp: 2,
        WebkitBoxOrient: "vertical",
        overflow: "hidden"
      }}>
        {preview}
      </div>
      
      {/* Brain Suggestion */}
      {hasSuggestion && message.status === "suggested" && (
        <div style={{
          padding: 12,
          background: `${GOLD}10`,
          border: `1px solid ${GOLD}30`,
          borderRadius: 8
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Brain size={14} color={GOLD} />
            <span style={{ fontSize: 11, color: GOLD, fontWeight: 500 }}>AI SUGGESTION</span>
            <span style={{ 
              fontSize: 10, 
              color: MU,
              marginLeft: "auto"
            }}>
              {Math.round((suggestion.confidence || 0) * 100)}% confident
            </span>
          </div>
          
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Zap size={14} color={GOLD2} />
            <span style={{ fontSize: 13, color: WH2 }}>
              {INTENT_LABELS[suggestion.intent] || suggestion.suggested_action || "Respond"}
            </span>
          </div>
          
          {suggestion.draft_response && (
            <div style={{ 
              fontSize: 12, 
              color: SV, 
              fontStyle: "italic",
              padding: "8px 10px",
              background: OB,
              borderRadius: 6,
              marginBottom: 10
            }}>
              "{suggestion.draft_response.substring(0, 150)}{suggestion.draft_response.length > 150 ? "..." : ""}"
            </div>
          )}
          
          {/* Action Buttons */}
          <div style={{ display: "flex", gap: 8 }} onClick={e => e.stopPropagation()}>
            <button
              onClick={() => onApprove(message.message_id)}
              data-testid={`approve-${message.message_id}`}
              style={{
                flex: 1,
                padding: "8px 12px",
                background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
                border: "none",
                borderRadius: 6,
                color: OB,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6
              }}
            >
              <Check size={14} />
              Approve
            </button>
            <button
              onClick={() => onReject(message.message_id)}
              data-testid={`reject-${message.message_id}`}
              style={{
                padding: "8px 12px",
                background: "rgba(239,68,68,.1)",
                border: "1px solid rgba(239,68,68,.3)",
                borderRadius: 6,
                color: "#ef4444",
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              <X size={14} />
            </button>
            <button
              onClick={() => onArchive(message.message_id)}
              style={{
                padding: "8px 12px",
                background: "rgba(107,114,128,.1)",
                border: "1px solid rgba(107,114,128,.3)",
                borderRadius: 6,
                color: "#6b7280",
                fontSize: 12,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}
            >
              <Archive size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageDetail({ message, onApprove, onReject, onArchive, onRegenerate }) {
  if (!message) {
    return (
      <div style={{ 
        display: "flex", 
        flexDirection: "column", 
        alignItems: "center", 
        justifyContent: "center",
        height: "100%",
        color: MU
      }}>
        <Inbox size={48} style={{ marginBottom: 16 }} />
        <p style={{ fontSize: 14 }}>Select a message to view details</p>
      </div>
    );
  }
  
  const channel = CHANNEL_CONFIG[message.channel] || CHANNEL_CONFIG.web_chat;
  const ChannelIcon = channel.icon;
  const suggestion = message.brain_suggestion;
  const senderName = message.sender?.name || "Unknown";
  const senderContact = message.sender?.email || message.sender?.phone || "";
  
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ 
        padding: 20, 
        borderBottom: `1px solid rgba(201,168,76,.1)`,
        background: OB3
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
          <div style={{
            width: 44, height: 44,
            borderRadius: 10,
            background: `${channel.color}20`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}>
            <ChannelIcon size={22} color={channel.color} />
          </div>
          <div>
            <div style={{ color: WH2, fontSize: 16, fontWeight: 500 }}>{senderName}</div>
            <div style={{ color: MU, fontSize: 12 }}>{senderContact}</div>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right" }}>
            <div style={{ fontSize: 11, color: MU }}>
              {new Date(message.received_at).toLocaleString()}
            </div>
            <div style={{ 
              fontSize: 10, 
              color: channel.color,
              marginTop: 2
            }}>
              via {channel.label}
            </div>
          </div>
        </div>
        
        {message.content?.subject && (
          <div style={{ fontSize: 14, color: WH2, fontWeight: 500 }}>
            {message.content.subject}
          </div>
        )}
      </div>
      
      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        <div style={{ 
          fontSize: 14, 
          color: SV, 
          lineHeight: 1.7,
          whiteSpace: "pre-wrap"
        }}>
          {message.content?.body || message.content?.text || "No content"}
        </div>
      </div>
      
      {/* Brain Suggestion Panel */}
      {suggestion && (
        <div style={{ 
          padding: 20, 
          borderTop: `1px solid rgba(201,168,76,.1)`,
          background: `${GOLD}08`
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <Brain size={20} color={GOLD} />
            <span style={{ color: GOLD2, fontSize: 14, fontWeight: 600 }}>Brain Suggestion</span>
            <span style={{ 
              marginLeft: "auto",
              padding: "4px 10px",
              background: `${GOLD}20`,
              borderRadius: 12,
              fontSize: 11,
              color: GOLD
            }}>
              {Math.round((suggestion.confidence || 0) * 100)}% confident
            </span>
          </div>
          
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            gap: 10,
            padding: 12,
            background: OB3,
            borderRadius: 8,
            marginBottom: 12
          }}>
            <Zap size={18} color={GOLD2} />
            <div>
              <div style={{ color: WH2, fontSize: 14, fontWeight: 500 }}>
                {INTENT_LABELS[suggestion.intent] || suggestion.suggested_action || "Reply"}
              </div>
              {suggestion.reasoning && (
                <div style={{ color: MU, fontSize: 11, marginTop: 2 }}>
                  {suggestion.reasoning}
                </div>
              )}
            </div>
          </div>
          
          {suggestion.draft_response && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, color: MU, marginBottom: 6 }}>DRAFT RESPONSE</div>
              <div style={{ 
                padding: 12, 
                background: OB, 
                borderRadius: 8,
                fontSize: 13,
                color: SV,
                lineHeight: 1.6
              }}>
                {suggestion.draft_response}
              </div>
            </div>
          )}
          
          {/* Action Buttons */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => onApprove(message.message_id)}
              data-testid="detail-approve-btn"
              style={{
                flex: 1,
                padding: "12px 20px",
                background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
                border: "none",
                borderRadius: 8,
                color: OB,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8
              }}
            >
              <Check size={16} />
              Approve Action
            </button>
            <button
              onClick={() => onReject(message.message_id)}
              style={{
                padding: "12px 20px",
                background: "rgba(239,68,68,.1)",
                border: "1px solid rgba(239,68,68,.3)",
                borderRadius: 8,
                color: "#ef4444",
                fontSize: 13,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6
              }}
            >
              <X size={16} />
              Reject
            </button>
            <button
              onClick={() => onRegenerate(message.message_id)}
              style={{
                padding: "12px 20px",
                background: "rgba(168,176,192,.1)",
                border: "1px solid rgba(168,176,192,.3)",
                borderRadius: 8,
                color: SV,
                fontSize: 13,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6
              }}
            >
              <RefreshCw size={16} />
              Regenerate
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function getTimeAgo(date) {
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString();
}

export default function UnifiedInbox({ businessId }) {
  const [messages, setMessages] = useState([]);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ channel: null, status: null });
  const [syncing, setSyncing] = useState(false);
  const wsRef = useRef(null);
  
  const fetchInbox = useCallback(async () => {
    if (!businessId) return;
    
    try {
      let url = `${API_BASE}/api/inbox/${businessId}?limit=100`;
      if (filter.channel) url += `&channel=${filter.channel}`;
      if (filter.status) url += `&status=${filter.status}`;
      
      const res = await fetch(url);
      const data = await res.json();
      
      setMessages(data.messages || []);
      setStats(data.stats);
      
      if (data.messages?.length > 0 && !selectedMessage) {
        setSelectedMessage(data.messages[0]);
      }
    } catch (err) {
      console.error("Failed to fetch inbox:", err);
    } finally {
      setLoading(false);
    }
  }, [businessId, filter, selectedMessage]);
  
  useEffect(() => {
    fetchInbox();
  }, [fetchInbox]);
  
  // WebSocket connection for real-time updates
  useEffect(() => {
    if (!businessId) return;
    
    const wsUrl = `${API_BASE.replace('http', 'ws')}/ws/aurem/${businessId}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "inbox_message") {
          if (data.action === "new") {
            setMessages(prev => [data.message, ...prev]);
          } else if (data.action === "update") {
            setMessages(prev => prev.map(m => 
              m.message_id === data.message_id 
                ? { ...m, status: data.status }
                : m
            ));
          }
        }
      };
      
      ws.onerror = () => {
        console.log("WebSocket connection failed - real-time updates disabled");
      };
      
      return () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch (e) {
      console.log("WebSocket not available");
    }
  }, [businessId]);
  
  const syncGmail = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_BASE}/api/inbox/${businessId}/sync/gmail`, {
        method: "POST"
      });
      const data = await res.json();
      
      if (data.synced_count > 0) {
        await fetchInbox();
      }
    } catch (err) {
      console.error("Gmail sync failed:", err);
    } finally {
      setSyncing(false);
    }
  };
  
  const handleApprove = async (messageId) => {
    try {
      const res = await fetch(`${API_BASE}/api/inbox/${businessId}/message/${messageId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      
      if (res.ok) {
        await fetchInbox();
      }
    } catch (err) {
      console.error("Approve failed:", err);
    }
  };
  
  const handleReject = async (messageId) => {
    try {
      const res = await fetch(`${API_BASE}/api/inbox/${businessId}/message/${messageId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      
      if (res.ok) {
        await fetchInbox();
      }
    } catch (err) {
      console.error("Reject failed:", err);
    }
  };
  
  const handleArchive = async (messageId) => {
    try {
      const res = await fetch(`${API_BASE}/api/inbox/${businessId}/message/${messageId}/archive`, {
        method: "POST"
      });
      
      if (res.ok) {
        setMessages(prev => prev.filter(m => m.message_id !== messageId));
        if (selectedMessage?.message_id === messageId) {
          setSelectedMessage(null);
        }
      }
    } catch (err) {
      console.error("Archive failed:", err);
    }
  };
  
  const handleRegenerate = async (messageId) => {
    try {
      const res = await fetch(`${API_BASE}/api/inbox/${businessId}/message/${messageId}/regenerate`, {
        method: "POST"
      });
      
      if (res.ok) {
        await fetchInbox();
      }
    } catch (err) {
      console.error("Regenerate failed:", err);
    }
  };
  
  if (loading) {
    return (
      <div style={{ padding: 24, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: MU }}>
          <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} />
          <span>Loading inbox...</span>
        </div>
      </div>
    );
  }
  
  const pendingCount = stats?.pending_actions || messages.filter(m => m.status === "suggested").length;
  
  return (
    <div data-testid="unified-inbox" style={{ height: "calc(100vh - 120px)", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{ 
        padding: "16px 20px", 
        borderBottom: `1px solid rgba(201,168,76,.1)`,
        display: "flex",
        alignItems: "center",
        gap: 16
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Inbox size={22} color={GOLD} />
          <h2 style={{ color: GOLD2, fontSize: 18, margin: 0, letterSpacing: "0.05em" }}>
            Unified Inbox
          </h2>
          {pendingCount > 0 && (
            <span style={{
              padding: "4px 10px",
              background: `${GOLD}20`,
              borderRadius: 12,
              fontSize: 11,
              fontWeight: 600,
              color: GOLD
            }}>
              {pendingCount} pending
            </span>
          )}
        </div>
        
        {/* Filters */}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <select
            value={filter.channel || ""}
            onChange={e => setFilter(f => ({ ...f, channel: e.target.value || null }))}
            style={{
              padding: "8px 12px",
              background: OB3,
              border: `1px solid rgba(201,168,76,.1)`,
              borderRadius: 6,
              color: SV,
              fontSize: 12
            }}
          >
            <option value="">All Channels</option>
            <option value="gmail">Gmail</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="web_chat">Web Chat</option>
          </select>
          
          <select
            value={filter.status || ""}
            onChange={e => setFilter(f => ({ ...f, status: e.target.value || null }))}
            style={{
              padding: "8px 12px",
              background: OB3,
              border: `1px solid rgba(201,168,76,.1)`,
              borderRadius: 6,
              color: SV,
              fontSize: 12
            }}
          >
            <option value="">All Status</option>
            <option value="suggested">With Suggestions</option>
            <option value="new">New</option>
            <option value="actioned">Actioned</option>
          </select>
          
          <button
            onClick={syncGmail}
            disabled={syncing}
            data-testid="sync-gmail-btn"
            style={{
              padding: "8px 16px",
              background: syncing ? OB3 : "rgba(234,67,53,.1)",
              border: "1px solid rgba(234,67,53,.3)",
              borderRadius: 6,
              color: "#ea4335",
              fontSize: 12,
              cursor: syncing ? "wait" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <RefreshCw size={14} style={{ animation: syncing ? "spin 1s linear infinite" : "none" }} />
            Sync Gmail
          </button>
        </div>
      </div>
      
      {/* Stats Bar */}
      {stats && (
        <div style={{ 
          padding: "12px 20px", 
          borderBottom: `1px solid rgba(201,168,76,.05)`,
          display: "flex",
          gap: 20,
          fontSize: 11,
          color: MU
        }}>
          <span>Total: <b style={{ color: WH2 }}>{stats.total}</b></span>
          {Object.entries(stats.by_channel || {}).map(([ch, count]) => (
            <span key={ch}>
              {CHANNEL_CONFIG[ch]?.label || ch}: <b style={{ color: CHANNEL_CONFIG[ch]?.color }}>{count}</b>
            </span>
          ))}
        </div>
      )}
      
      {/* Main Content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Message List */}
        <div style={{ 
          width: 400, 
          borderRight: `1px solid rgba(201,168,76,.1)`,
          overflow: "auto",
          padding: 12
        }}>
          {messages.length === 0 ? (
            <div style={{ 
              padding: 40, 
              textAlign: "center",
              color: MU
            }}>
              <Inbox size={40} style={{ marginBottom: 12, opacity: 0.5 }} />
              <p style={{ fontSize: 13 }}>No messages yet</p>
              <p style={{ fontSize: 11 }}>Sync your Gmail or wait for incoming messages</p>
            </div>
          ) : (
            messages.map(message => (
              <MessageCard
                key={message.message_id}
                message={message}
                isSelected={selectedMessage?.message_id === message.message_id}
                onSelect={() => setSelectedMessage(message)}
                onApprove={handleApprove}
                onReject={handleReject}
                onArchive={handleArchive}
              />
            ))
          )}
        </div>
        
        {/* Message Detail */}
        <div style={{ flex: 1, background: OB2 }}>
          <MessageDetail
            message={selectedMessage}
            onApprove={handleApprove}
            onReject={handleReject}
            onArchive={handleArchive}
            onRegenerate={handleRegenerate}
          />
        </div>
      </div>
      
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
