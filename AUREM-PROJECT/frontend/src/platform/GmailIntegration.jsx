/**
 * AUREM Gmail Integration Component
 * Allows businesses to connect their Gmail accounts and view/send emails
 */

import { useState, useEffect, useCallback } from "react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

export default function GmailIntegration({ businessId }) {
  const [connectionStatus, setConnectionStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [showCompose, setShowCompose] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("INBOX");
  const [profile, setProfile] = useState(null);
  
  // Compose form state
  const [composeTo, setComposeTo] = useState("");
  const [composeSubject, setComposeSubject] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [sending, setSending] = useState(false);
  
  // Check connection status
  const checkStatus = useCallback(async () => {
    if (!businessId) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/oauth/gmail/status/${businessId}`);
      const data = await res.json();
      setConnectionStatus(data);
      
      if (data.connected) {
        // Fetch profile
        const profileRes = await fetch(`${API_BASE}/api/gmail/${businessId}/profile`);
        if (profileRes.ok) {
          const profileData = await profileRes.json();
          setProfile(profileData);
        }
      }
    } catch (err) {
      console.error("Failed to check Gmail status:", err);
    } finally {
      setLoading(false);
    }
  }, [businessId]);
  
  // Fetch emails
  const fetchEmails = useCallback(async (query = "", labelIds = "INBOX") => {
    if (!businessId || !connectionStatus?.connected) return;
    
    try {
      let url = `${API_BASE}/api/gmail/${businessId}/messages?max_results=20&label_ids=${labelIds}`;
      if (query) url += `&query=${encodeURIComponent(query)}`;
      
      const res = await fetch(url);
      const data = await res.json();
      
      if (data.messages) {
        // Fetch details for each message
        const detailed = await Promise.all(
          data.messages.slice(0, 10).map(async (m) => {
            try {
              const detailRes = await fetch(`${API_BASE}/api/gmail/${businessId}/messages/${m.id}`);
              return detailRes.ok ? await detailRes.json() : null;
            } catch {
              return null;
            }
          })
        );
        setMessages(detailed.filter(Boolean));
      }
    } catch (err) {
      console.error("Failed to fetch emails:", err);
    }
  }, [businessId, connectionStatus?.connected]);
  
  useEffect(() => {
    checkStatus();
    
    // Check for OAuth callback params
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail_connected")) {
      checkStatus();
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
    if (params.get("gmail_error")) {
      alert("Gmail connection failed: " + params.get("gmail_error"));
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [checkStatus]);
  
  useEffect(() => {
    if (connectionStatus?.connected) {
      fetchEmails(searchQuery, activeFilter);
    }
  }, [connectionStatus?.connected, fetchEmails, activeFilter, searchQuery]);
  
  // Connect Gmail
  const handleConnect = () => {
    const redirectUrl = encodeURIComponent(window.location.href);
    window.location.href = `${API_BASE}/api/oauth/gmail/authorize?business_id=${businessId}&redirect_url=${redirectUrl}`;
  };
  
  // Disconnect Gmail
  const handleDisconnect = async () => {
    if (!confirm("Are you sure you want to disconnect Gmail?")) return;
    
    try {
      await fetch(`${API_BASE}/api/oauth/gmail/disconnect/${businessId}`, { method: "DELETE" });
      setConnectionStatus({ ...connectionStatus, connected: false });
      setMessages([]);
      setProfile(null);
    } catch (err) {
      console.error("Failed to disconnect:", err);
    }
  };
  
  // Send email
  const handleSend = async (e) => {
    e.preventDefault();
    if (!composeTo || !composeSubject || !composeBody) return;
    
    setSending(true);
    try {
      const res = await fetch(`${API_BASE}/api/gmail/${businessId}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: composeTo,
          subject: composeSubject,
          body_text: composeBody
        })
      });
      
      const data = await res.json();
      if (data.success) {
        setShowCompose(false);
        setComposeTo("");
        setComposeSubject("");
        setComposeBody("");
        // Refresh inbox
        fetchEmails(searchQuery, activeFilter);
      } else {
        alert("Failed to send: " + (data.error || "Unknown error"));
      }
    } catch (err) {
      console.error("Send failed:", err);
      alert("Failed to send email");
    } finally {
      setSending(false);
    }
  };
  
  // Mark as read
  const handleMarkRead = async (messageId) => {
    try {
      await fetch(`${API_BASE}/api/gmail/${businessId}/messages/${messageId}/read`, { method: "PUT" });
      // Update local state
      setMessages(msgs => msgs.map(m => 
        m.id === messageId ? { ...m, label_ids: m.label_ids.filter(l => l !== "UNREAD") } : m
      ));
    } catch (err) {
      console.error("Failed to mark as read:", err);
    }
  };
  
  // Archive
  const handleArchive = async (messageId) => {
    try {
      await fetch(`${API_BASE}/api/gmail/${businessId}/messages/${messageId}/archive`, { method: "PUT" });
      setMessages(msgs => msgs.filter(m => m.id !== messageId));
      setSelectedMessage(null);
    } catch (err) {
      console.error("Failed to archive:", err);
    }
  };
  
  if (loading) {
    return (
      <div style={{ padding: 24, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 300 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 20, height: 20, border: `2px solid ${GOLD}`, borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
          <span style={{ color: MU }}>Loading Gmail integration...</span>
        </div>
      </div>
    );
  }
  
  // Not connected view
  if (!connectionStatus?.connected) {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Gmail Integration</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Connect your Gmail account to read and send emails through AUREM</p>
        </div>
        
        <div style={{ 
          display: "flex", 
          flexDirection: "column", 
          alignItems: "center", 
          justifyContent: "center", 
          padding: 60, 
          background: OB3, 
          border: `1px solid rgba(201,168,76,.1)`, 
          borderRadius: 16 
        }}>
          <div style={{ 
            width: 80, 
            height: 80, 
            background: "linear-gradient(135deg, #EA4335, #FBBC04, #34A853, #4285F4)", 
            borderRadius: 20, 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            marginBottom: 24,
            boxShadow: "0 8px 32px rgba(66,133,244,.3)"
          }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="white">
              <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/>
            </svg>
          </div>
          
          <h3 style={{ fontSize: 18, color: WH2, margin: "0 0 8px", letterSpacing: "0.05em" }}>
            Connect Your Gmail Account
          </h3>
          <p style={{ fontSize: 13, color: MU, textAlign: "center", maxWidth: 400, marginBottom: 24, lineHeight: 1.6 }}>
            Allow AUREM to read and send emails on your behalf. Your credentials are encrypted with AES-256 and never stored in plain text.
          </p>
          
          <button
            onClick={handleConnect}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "14px 32px",
              background: "linear-gradient(135deg, #4285F4, #357abd)",
              border: "none",
              borderRadius: 8,
              color: "#fff",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 4px 16px rgba(66,133,244,.4)",
              transition: "transform 0.2s, box-shadow 0.2s"
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow = "0 6px 20px rgba(66,133,244,.5)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 4px 16px rgba(66,133,244,.4)";
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Connect with Google
          </button>
          
          <div style={{ marginTop: 32, display: "flex", gap: 24, color: MU, fontSize: 11 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#4ade80" }}>✓</span> AES-256 Encryption
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#4ade80" }}>✓</span> Revoke Anytime
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#4ade80" }}>✓</span> PIPEDA Compliant
            </div>
          </div>
        </div>
      </div>
    );
  }
  
  // Connected view
  return (
    <div style={{ padding: 24 }}>
      <style>{`
        @keyframes spin{to{transform:rotate(360deg)}}
      `}</style>
      
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Gmail Integration</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>
            Connected as <span style={{ color: GOLD }}>{connectionStatus.email}</span>
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button
            onClick={() => setShowCompose(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "10px 20px",
              background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
              border: "none",
              borderRadius: 8,
              color: OB,
              fontWeight: 600,
              cursor: "pointer",
              fontSize: 12
            }}
          >
            <span style={{ fontSize: 16 }}>+</span>
            Compose
          </button>
          <button
            onClick={handleDisconnect}
            style={{
              padding: "10px 16px",
              background: "rgba(239,68,68,.1)",
              border: "1px solid rgba(239,68,68,.3)",
              borderRadius: 8,
              color: "#ef4444",
              fontSize: 12,
              cursor: "pointer"
            }}
          >
            Disconnect
          </button>
        </div>
      </div>
      
      {/* Stats */}
      {profile && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace" }}>{profile.messages_total?.toLocaleString() || 0}</div>
            <div style={{ fontSize: 10, color: MU, marginTop: 4 }}>Total Messages</div>
          </div>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace" }}>{profile.threads_total?.toLocaleString() || 0}</div>
            <div style={{ fontSize: 10, color: MU, marginTop: 4 }}>Threads</div>
          </div>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: "#4ade80", fontFamily: "monospace" }}>Active</div>
            <div style={{ fontSize: 10, color: MU, marginTop: 4 }}>Connection Status</div>
          </div>
        </div>
      )}
      
      {/* Search & Filters */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <input
          type="text"
          placeholder="Search emails..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          onKeyDown={e => e.key === "Enter" && fetchEmails(searchQuery, activeFilter)}
          style={{
            flex: 1,
            padding: "10px 16px",
            background: OB3,
            border: `1px solid rgba(201,168,76,.1)`,
            borderRadius: 8,
            color: WH2,
            fontSize: 13,
            outline: "none"
          }}
        />
        {["INBOX", "SENT", "STARRED", "UNREAD"].map(filter => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            style={{
              padding: "10px 16px",
              background: activeFilter === filter ? `rgba(201,168,76,.15)` : "transparent",
              border: `1px solid ${activeFilter === filter ? GOLD : "rgba(201,168,76,.1)"}`,
              borderRadius: 8,
              color: activeFilter === filter ? GOLD : MU,
              fontSize: 11,
              cursor: "pointer",
              letterSpacing: "0.05em"
            }}
          >
            {filter}
          </button>
        ))}
      </div>
      
      {/* Email List */}
      <div style={{ display: "grid", gridTemplateColumns: selectedMessage ? "1fr 1fr" : "1fr", gap: 16 }}>
        <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 11, color: MU, letterSpacing: "0.08em" }}>
            {messages.length} MESSAGE{messages.length !== 1 ? "S" : ""}
          </div>
          
          {messages.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: MU }}>
              No messages found
            </div>
          ) : (
            messages.map(msg => (
              <div
                key={msg.id}
                onClick={() => {
                  setSelectedMessage(msg);
                  if (msg.label_ids?.includes("UNREAD")) handleMarkRead(msg.id);
                }}
                style={{
                  padding: "14px 16px",
                  borderBottom: `1px solid rgba(201,168,76,.05)`,
                  cursor: "pointer",
                  background: selectedMessage?.id === msg.id ? "rgba(201,168,76,.08)" : "transparent",
                  transition: "background 0.2s"
                }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(201,168,76,.05)"}
                onMouseLeave={e => e.currentTarget.style.background = selectedMessage?.id === msg.id ? "rgba(201,168,76,.08)" : "transparent"}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <span style={{ 
                    fontSize: 13, 
                    color: msg.label_ids?.includes("UNREAD") ? WH2 : SV,
                    fontWeight: msg.label_ids?.includes("UNREAD") ? 600 : 400
                  }}>
                    {msg.from?.split("<")[0]?.trim() || msg.from || "Unknown"}
                  </span>
                  <span style={{ fontSize: 10, color: MU }}>
                    {msg.date ? new Date(msg.date).toLocaleDateString() : ""}
                  </span>
                </div>
                <div style={{ 
                  fontSize: 12, 
                  color: msg.label_ids?.includes("UNREAD") ? GOLD2 : SV,
                  marginBottom: 4,
                  fontWeight: msg.label_ids?.includes("UNREAD") ? 500 : 400
                }}>
                  {msg.subject || "(No subject)"}
                </div>
                <div style={{ fontSize: 11, color: MU, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {msg.snippet || msg.body_text?.slice(0, 100) || ""}
                </div>
                {msg.label_ids?.includes("UNREAD") && (
                  <div style={{ 
                    display: "inline-block", 
                    width: 8, 
                    height: 8, 
                    background: GOLD, 
                    borderRadius: "50%", 
                    marginTop: 6,
                    boxShadow: `0 0 8px ${GOLD}`
                  }} />
                )}
              </div>
            ))
          )}
        </div>
        
        {/* Message Detail */}
        {selectedMessage && (
          <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "16px", borderBottom: `1px solid rgba(201,168,76,.1)` }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3 style={{ fontSize: 14, color: WH2, margin: "0 0 8px" }}>{selectedMessage.subject || "(No subject)"}</h3>
                  <p style={{ fontSize: 12, color: SV, margin: 0 }}>
                    From: {selectedMessage.from}
                  </p>
                  <p style={{ fontSize: 11, color: MU, margin: "4px 0 0" }}>
                    To: {selectedMessage.to}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedMessage(null)}
                  style={{ 
                    padding: "6px 12px", 
                    background: "transparent", 
                    border: `1px solid rgba(201,168,76,.2)`, 
                    borderRadius: 6, 
                    color: MU, 
                    fontSize: 10, 
                    cursor: "pointer" 
                  }}
                >
                  Close
                </button>
              </div>
            </div>
            
            <div style={{ flex: 1, padding: 16, overflow: "auto", fontSize: 13, color: SV, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
              {selectedMessage.body_text || selectedMessage.snippet || "No content"}
            </div>
            
            <div style={{ padding: "12px 16px", borderTop: `1px solid rgba(201,168,76,.1)`, display: "flex", gap: 8 }}>
              <button
                onClick={() => {
                  setShowCompose(true);
                  setComposeTo(selectedMessage.from?.match(/<(.+?)>/)?.[1] || selectedMessage.from || "");
                  setComposeSubject(`Re: ${selectedMessage.subject || ""}`);
                }}
                style={{ flex: 1, padding: "10px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 6, color: OB, fontWeight: 600, fontSize: 11, cursor: "pointer" }}
              >
                Reply
              </button>
              <button
                onClick={() => handleArchive(selectedMessage.id)}
                style={{ padding: "10px 16px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 11, cursor: "pointer" }}
              >
                Archive
              </button>
            </div>
          </div>
        )}
      </div>
      
      {/* Compose Modal */}
      {showCompose && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,.8)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 10000
        }}>
          <div style={{
            background: OB,
            border: `1px solid rgba(201,168,76,.2)`,
            borderRadius: 16,
            width: "100%",
            maxWidth: 600,
            maxHeight: "80vh",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column"
          }}>
            <div style={{ padding: "16px 20px", borderBottom: `1px solid rgba(201,168,76,.1)`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0, fontSize: 16, color: GOLD2 }}>Compose Email</h3>
              <button
                onClick={() => setShowCompose(false)}
                style={{ background: "transparent", border: "none", color: MU, fontSize: 20, cursor: "pointer", padding: 4 }}
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSend} style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
                <input
                  type="email"
                  placeholder="To"
                  value={composeTo}
                  onChange={e => setComposeTo(e.target.value)}
                  required
                  style={{
                    padding: "12px 16px",
                    background: OB3,
                    border: `1px solid rgba(201,168,76,.1)`,
                    borderRadius: 8,
                    color: WH2,
                    fontSize: 13,
                    outline: "none"
                  }}
                />
                <input
                  type="text"
                  placeholder="Subject"
                  value={composeSubject}
                  onChange={e => setComposeSubject(e.target.value)}
                  required
                  style={{
                    padding: "12px 16px",
                    background: OB3,
                    border: `1px solid rgba(201,168,76,.1)`,
                    borderRadius: 8,
                    color: WH2,
                    fontSize: 13,
                    outline: "none"
                  }}
                />
              </div>
              
              <textarea
                placeholder="Write your message..."
                value={composeBody}
                onChange={e => setComposeBody(e.target.value)}
                required
                style={{
                  flex: 1,
                  margin: "0 20px",
                  padding: 16,
                  background: OB3,
                  border: `1px solid rgba(201,168,76,.1)`,
                  borderRadius: 8,
                  color: WH2,
                  fontSize: 13,
                  resize: "none",
                  outline: "none",
                  minHeight: 200
                }}
              />
              
              <div style={{ padding: "16px 20px", borderTop: `1px solid rgba(201,168,76,.1)`, display: "flex", justifyContent: "flex-end", gap: 12 }}>
                <button
                  type="button"
                  onClick={() => setShowCompose(false)}
                  style={{
                    padding: "10px 24px",
                    background: "transparent",
                    border: `1px solid rgba(201,168,76,.2)`,
                    borderRadius: 8,
                    color: MU,
                    fontSize: 12,
                    cursor: "pointer"
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sending}
                  style={{
                    padding: "10px 24px",
                    background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
                    border: "none",
                    borderRadius: 8,
                    color: OB,
                    fontWeight: 600,
                    fontSize: 12,
                    cursor: sending ? "not-allowed" : "pointer",
                    opacity: sending ? 0.7 : 1
                  }}
                >
                  {sending ? "Sending..." : "Send"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
