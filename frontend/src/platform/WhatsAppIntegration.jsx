import { useState, useEffect, useCallback } from "react";
import { 
  MessageCircle, Check, X, RefreshCw, ExternalLink, 
  Phone, Send, Shield, AlertCircle, Copy, CheckCircle,
  Settings, Zap, Globe, Link2
} from "lucide-react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const WA_GREEN = "#25D366";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

function StatusBadge({ connected, status }) {
  const config = {
    connected: { color: WA_GREEN, label: "Connected", icon: CheckCircle },
    pending: { color: "#f59e0b", label: "Pending Setup", icon: AlertCircle },
    disconnected: { color: "#6b7280", label: "Disconnected", icon: X },
    not_configured: { color: MU, label: "Not Connected", icon: AlertCircle },
    error: { color: "#ef4444", label: "Error", icon: AlertCircle }
  };
  
  const c = config[status] || config.not_configured;
  const Icon = c.icon;
  
  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "6px 12px",
      background: `${c.color}20`,
      borderRadius: 20,
      fontSize: 12,
      fontWeight: 500,
      color: c.color
    }}>
      <Icon size={14} />
      {c.label}
    </div>
  );
}

function SetupStep({ number, title, description, completed, active, children }) {
  return (
    <div style={{
      padding: 20,
      background: active ? `${GOLD}08` : OB3,
      border: `1px solid ${active ? GOLD : completed ? WA_GREEN : 'rgba(201,168,76,.1)'}`,
      borderRadius: 12,
      marginBottom: 16,
      opacity: completed && !active ? 0.7 : 1
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
        <div style={{
          width: 32, height: 32,
          borderRadius: "50%",
          background: completed ? `${WA_GREEN}20` : active ? `${GOLD}20` : OB,
          border: `2px solid ${completed ? WA_GREEN : active ? GOLD : MU}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0
        }}>
          {completed ? (
            <Check size={16} color={WA_GREEN} />
          ) : (
            <span style={{ fontSize: 14, fontWeight: 600, color: active ? GOLD : MU }}>{number}</span>
          )}
        </div>
        <div style={{ flex: 1 }}>
          <h4 style={{ color: WH2, fontSize: 14, margin: "0 0 4px", fontWeight: 600 }}>{title}</h4>
          <p style={{ color: MU, fontSize: 12, margin: 0, lineHeight: 1.5 }}>{description}</p>
          {children && <div style={{ marginTop: 16 }}>{children}</div>}
        </div>
      </div>
    </div>
  );
}

function WebhookConfig({ businessId }) {
  const [config, setConfig] = useState(null);
  const [copied, setCopied] = useState(null);
  
  useEffect(() => {
    fetch(`${API_BASE}/api/whatsapp/${businessId}/verify-token`)
      .then(r => r.json())
      .then(setConfig)
      .catch(console.error);
  }, [businessId]);
  
  const copyToClipboard = async (text, field) => {
    await navigator.clipboard.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(null), 2000);
  };
  
  if (!config) return null;
  
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, color: MU, marginBottom: 8 }}>WEBHOOK CONFIGURATION</div>
      
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 10, color: GDIM, display: "block", marginBottom: 4 }}>Callback URL</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={config.webhook_url}
            readOnly
            style={{
              flex: 1,
              padding: "10px 12px",
              background: OB,
              border: "1px solid rgba(201,168,76,.1)",
              borderRadius: 6,
              color: SV,
              fontSize: 12,
              fontFamily: "monospace"
            }}
          />
          <button
            onClick={() => copyToClipboard(config.webhook_url, "url")}
            style={{
              padding: "0 12px",
              background: copied === "url" ? `${WA_GREEN}20` : "rgba(201,168,76,.1)",
              border: "none",
              borderRadius: 6,
              cursor: "pointer"
            }}
          >
            {copied === "url" ? <Check size={14} color={WA_GREEN} /> : <Copy size={14} color={GDIM} />}
          </button>
        </div>
      </div>
      
      <div>
        <label style={{ fontSize: 10, color: GDIM, display: "block", marginBottom: 4 }}>Verify Token</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            type="text"
            value={config.verify_token}
            readOnly
            style={{
              flex: 1,
              padding: "10px 12px",
              background: OB,
              border: "1px solid rgba(201,168,76,.1)",
              borderRadius: 6,
              color: SV,
              fontSize: 12,
              fontFamily: "monospace"
            }}
          />
          <button
            onClick={() => copyToClipboard(config.verify_token, "token")}
            style={{
              padding: "0 12px",
              background: copied === "token" ? `${WA_GREEN}20` : "rgba(201,168,76,.1)",
              border: "none",
              borderRadius: 6,
              cursor: "pointer"
            }}
          >
            {copied === "token" ? <Check size={14} color={WA_GREEN} /> : <Copy size={14} color={GDIM} />}
          </button>
        </div>
      </div>
      
      <p style={{ fontSize: 11, color: MU, marginTop: 12 }}>
        {config.instructions}
      </p>
    </div>
  );
}

function SendTestMessage({ businessId, onSent }) {
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("Hello from AUREM! This is a test message.");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  
  const handleSend = async () => {
    if (!phone || !message) return;
    
    setSending(true);
    setResult(null);
    
    try {
      const res = await fetch(`${API_BASE}/api/whatsapp/${businessId}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ to: phone, text: message })
      });
      
      const data = await res.json();
      
      if (data.success) {
        setResult({ success: true, message_id: data.message_id });
        if (onSent) onSent();
      } else {
        setResult({ error: data.error || "Failed to send" });
      }
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setSending(false);
    }
  };
  
  return (
    <div style={{ marginTop: 20, padding: 16, background: OB, borderRadius: 8 }}>
      <div style={{ fontSize: 12, color: GOLD, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
        <Send size={14} />
        Send Test Message
      </div>
      
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 10, color: MU, display: "block", marginBottom: 4 }}>Phone Number (E.164)</label>
        <input
          type="text"
          placeholder="+1234567890"
          value={phone}
          onChange={e => setPhone(e.target.value)}
          style={{
            width: "100%",
            padding: "10px 12px",
            background: OB3,
            border: "1px solid rgba(201,168,76,.1)",
            borderRadius: 6,
            color: WH2,
            fontSize: 13
          }}
        />
      </div>
      
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 10, color: MU, display: "block", marginBottom: 4 }}>Message</label>
        <textarea
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={3}
          style={{
            width: "100%",
            padding: "10px 12px",
            background: OB3,
            border: "1px solid rgba(201,168,76,.1)",
            borderRadius: 6,
            color: WH2,
            fontSize: 13,
            resize: "none"
          }}
        />
      </div>
      
      <button
        onClick={handleSend}
        disabled={!phone || !message || sending}
        style={{
          width: "100%",
          padding: "12px",
          background: phone && message ? WA_GREEN : OB3,
          border: "none",
          borderRadius: 6,
          color: phone && message ? "#fff" : MU,
          fontSize: 13,
          fontWeight: 600,
          cursor: phone && message && !sending ? "pointer" : "not-allowed",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8
        }}
      >
        {sending ? (
          <>
            <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} />
            Sending...
          </>
        ) : (
          <>
            <Send size={14} />
            Send Message
          </>
        )}
      </button>
      
      {result && (
        <div style={{
          marginTop: 12,
          padding: 10,
          background: result.success ? `${WA_GREEN}10` : "rgba(239,68,68,.1)",
          borderRadius: 6,
          fontSize: 12,
          color: result.success ? WA_GREEN : "#ef4444"
        }}>
          {result.success ? `Message sent! ID: ${result.message_id}` : result.error}
        </div>
      )}
    </div>
  );
}

export default function WhatsAppIntegration({ businessId }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [messages, setMessages] = useState([]);
  
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/whatsapp/${businessId}/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to fetch WhatsApp status:", err);
    } finally {
      setLoading(false);
    }
  }, [businessId]);
  
  const fetchMessages = useCallback(async () => {
    if (!status?.connected) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/whatsapp/${businessId}/messages?limit=10`);
      const data = await res.json();
      setMessages(data.messages || []);
    } catch (err) {
      console.error("Failed to fetch messages:", err);
    }
  }, [businessId, status?.connected]);
  
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);
  
  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);
  
  const handleConnect = async () => {
    setConnecting(true);
    try {
      const res = await fetch(`${API_BASE}/api/whatsapp/${businessId}/connect`, {
        method: "POST"
      });
      const data = await res.json();
      
      if (data.oauth_url) {
        // Open Meta Embedded Signup in new window
        window.open(data.oauth_url, "whatsapp_connect", "width=600,height=700");
        
        // Poll for connection completion
        const pollInterval = setInterval(async () => {
          const statusRes = await fetch(`${API_BASE}/api/whatsapp/${businessId}/status`);
          const statusData = await statusRes.json();
          
          if (statusData.connected) {
            clearInterval(pollInterval);
            setStatus(statusData);
            setConnecting(false);
          }
        }, 3000);
        
        // Stop polling after 5 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setConnecting(false);
        }, 300000);
      }
    } catch (err) {
      console.error("Connect failed:", err);
      setConnecting(false);
    }
  };
  
  const handleDisconnect = async () => {
    if (!confirm("Are you sure you want to disconnect WhatsApp?")) return;
    
    setDisconnecting(true);
    try {
      await fetch(`${API_BASE}/api/whatsapp/${businessId}/disconnect`, {
        method: "POST"
      });
      await fetchStatus();
    } catch (err) {
      console.error("Disconnect failed:", err);
    } finally {
      setDisconnecting(false);
    }
  };
  
  if (loading) {
    return (
      <div style={{ padding: 24, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 300 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: MU }}>
          <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} />
          <span>Loading WhatsApp status...</span>
        </div>
      </div>
    );
  }
  
  const isConnected = status?.connected;
  
  return (
    <div data-testid="whatsapp-integration" style={{ padding: 24, maxWidth: 800 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 56, height: 56,
            borderRadius: 12,
            background: `${WA_GREEN}20`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}>
            <MessageCircle size={28} color={WA_GREEN} />
          </div>
          <div>
            <h2 style={{ color: GOLD2, fontSize: 20, margin: 0, letterSpacing: "0.05em" }}>
              WhatsApp Business
            </h2>
            <p style={{ color: MU, fontSize: 12, margin: "4px 0 0" }}>
              Connect your WhatsApp Business account to receive messages in the Unified Inbox
            </p>
          </div>
        </div>
        <StatusBadge connected={isConnected} status={status?.status} />
      </div>
      
      {isConnected ? (
        /* Connected State */
        <div>
          {/* Connection Details */}
          <div style={{
            padding: 20,
            background: `${WA_GREEN}10`,
            border: `1px solid ${WA_GREEN}30`,
            borderRadius: 12,
            marginBottom: 24
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <CheckCircle size={20} color={WA_GREEN} />
              <span style={{ color: WA_GREEN, fontSize: 14, fontWeight: 600 }}>WhatsApp Connected</span>
            </div>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>PHONE NUMBER</div>
                <div style={{ fontSize: 14, color: WH2, fontFamily: "monospace" }}>
                  {status.display_phone_number || "Not available"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>WABA ID</div>
                <div style={{ fontSize: 14, color: WH2, fontFamily: "monospace" }}>
                  {status.waba_id || "Not available"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>CONNECTED</div>
                <div style={{ fontSize: 14, color: WH2 }}>
                  {status.connected_at ? new Date(status.connected_at).toLocaleDateString() : "N/A"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>PHONE NUMBER ID</div>
                <div style={{ fontSize: 14, color: WH2, fontFamily: "monospace" }}>
                  {status.phone_number_id || "Not available"}
                </div>
              </div>
            </div>
            
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              style={{
                marginTop: 16,
                padding: "8px 16px",
                background: "rgba(239,68,68,.1)",
                border: "1px solid rgba(239,68,68,.3)",
                borderRadius: 6,
                color: "#ef4444",
                fontSize: 12,
                cursor: disconnecting ? "wait" : "pointer"
              }}
            >
              {disconnecting ? "Disconnecting..." : "Disconnect WhatsApp"}
            </button>
          </div>
          
          {/* Send Test Message */}
          <SendTestMessage businessId={businessId} onSent={fetchMessages} />
          
          {/* Recent Messages */}
          {messages.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <h3 style={{ color: GOLD2, fontSize: 14, marginBottom: 12 }}>Recent Messages</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {messages.map((msg, i) => (
                  <div
                    key={msg.wa_message_id || i}
                    style={{
                      padding: 12,
                      background: OB3,
                      borderRadius: 8,
                      borderLeft: `3px solid ${msg.direction === "inbound" ? WA_GREEN : GOLD}`
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: msg.direction === "inbound" ? WA_GREEN : GOLD }}>
                        {msg.direction === "inbound" ? `From: ${msg.contact_name || msg.from_number}` : `To: ${msg.to_number}`}
                      </span>
                      <span style={{ fontSize: 10, color: MU }}>
                        {new Date(msg.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, color: SV }}>
                      {msg.content?.text || msg.content?.body || `[${msg.message_type}]`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Setup Flow */
        <div>
          <div style={{
            padding: 16,
            background: "rgba(245,158,11,.1)",
            border: "1px solid rgba(245,158,11,.3)",
            borderRadius: 8,
            marginBottom: 24,
            display: "flex",
            alignItems: "flex-start",
            gap: 12
          }}>
            <AlertCircle size={20} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ color: "#f59e0b", fontSize: 13, fontWeight: 500, marginBottom: 4 }}>
                Prerequisites
              </div>
              <ul style={{ color: SV, fontSize: 12, margin: 0, paddingLeft: 16, lineHeight: 1.6 }}>
                <li>A verified Meta Business Manager account</li>
                <li>A phone number not already linked to WhatsApp or WhatsApp Business app</li>
                <li>Two-factor authentication enabled on your Meta account</li>
              </ul>
            </div>
          </div>
          
          <SetupStep
            number={1}
            title="Configure Meta App"
            description="Set up your Meta App with WhatsApp permissions and configure the webhook endpoint."
            completed={false}
            active={true}
          >
            <WebhookConfig businessId={businessId} />
          </SetupStep>
          
          <SetupStep
            number={2}
            title="Connect WhatsApp Business Account"
            description="Use Meta Embedded Signup to connect your WhatsApp Business Account in under 2 minutes."
            completed={false}
            active={false}
          >
            <button
              onClick={handleConnect}
              disabled={connecting}
              data-testid="connect-whatsapp-btn"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "14px 24px",
                background: connecting ? OB3 : WA_GREEN,
                border: "none",
                borderRadius: 8,
                color: connecting ? MU : "#fff",
                fontSize: 14,
                fontWeight: 600,
                cursor: connecting ? "wait" : "pointer"
              }}
            >
              {connecting ? (
                <>
                  <RefreshCw size={18} style={{ animation: "spin 1s linear infinite" }} />
                  Waiting for Authorization...
                </>
              ) : (
                <>
                  <Link2 size={18} />
                  Connect with Meta
                  <ExternalLink size={14} />
                </>
              )}
            </button>
            
            {connecting && (
              <p style={{ fontSize: 12, color: MU, marginTop: 12 }}>
                Complete the authorization in the popup window. This page will update automatically.
              </p>
            )}
          </SetupStep>
          
          <SetupStep
            number={3}
            title="Start Receiving Messages"
            description="Once connected, incoming WhatsApp messages will appear in your Unified Inbox with AI-powered suggestions."
            completed={false}
            active={false}
          />
          
          {/* Features Preview */}
          <div style={{ marginTop: 32 }}>
            <h3 style={{ color: GOLD2, fontSize: 14, marginBottom: 16 }}>What You Get</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {[
                { icon: Zap, title: "AI-Powered Responses", desc: "Brain suggests actions for each message" },
                { icon: Globe, title: "Unified Inbox", desc: "WhatsApp alongside Gmail and Web Chat" },
                { icon: Shield, title: "Secure & Compliant", desc: "End-to-end encryption maintained" },
                { icon: Settings, title: "Template Messages", desc: "Send pre-approved templates anytime" }
              ].map((feature, i) => (
                <div
                  key={i}
                  style={{
                    padding: 16,
                    background: OB3,
                    borderRadius: 8,
                    border: "1px solid rgba(201,168,76,.05)"
                  }}
                >
                  <feature.icon size={20} color={WA_GREEN} style={{ marginBottom: 8 }} />
                  <div style={{ color: WH2, fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{feature.title}</div>
                  <div style={{ color: MU, fontSize: 11 }}>{feature.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
