/**
 * AUREM Voice Command Center (Phase 8)
 * Live Operations Dashboard for Voice AI Integration
 * 
 * Features:
 * - Live Call Feed: Real-time active calls with waveform visualization
 * - OODA Trace: Scrolling feed of AI "thinking" during calls
 * - Manual Override: Join Call / End Call buttons
 * - Call History: Recent calls with transcripts and actions
 * - Persona Selector: Switch between Luxe Skincare, Auto Advisor, etc.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { 
  Phone, PhoneCall, PhoneOff, PhoneMissed, PhoneIncoming, PhoneOutgoing,
  Mic, MicOff, Volume2, VolumeX, Brain, Zap, Clock, User, Calendar,
  Play, Pause, RefreshCw, Settings, ChevronRight, Activity,
  CheckCircle, XCircle, AlertCircle, Loader2
} from "lucide-react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

const STATUS_COLORS = {
  in_progress: "#4ade80",
  ringing: "#f59e0b",
  ended: "#6b7280",
  failed: "#ef4444"
};

const PERSONA_CONFIG = {
  skincare_luxe: { 
    name: "Luxe Skincare", 
    icon: "✨", 
    color: "#e2c97e",
    description: "Sophisticated PDRN technology expert"
  },
  auto_advisor: { 
    name: "Auto Advisor", 
    icon: "🚗", 
    color: "#60a5fa",
    description: "Technical service specialist"
  },
  general_assistant: { 
    name: "General Assistant", 
    icon: "🤖", 
    color: "#a855f7",
    description: "Professional business helper"
  }
};

// ═══════════════════════════════════════════════════════════════════════════════
// WAVEFORM VISUALIZATION
// ═══════════════════════════════════════════════════════════════════════════════

function LiveWaveform({ isActive }) {
  const bars = 20;
  
  return (
    <div style={{ 
      display: "flex", 
      alignItems: "center", 
      gap: 2, 
      height: 40,
      padding: "0 8px"
    }}>
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 3,
            height: isActive ? `${20 + Math.random() * 60}%` : "20%",
            background: isActive 
              ? `linear-gradient(180deg, ${GOLD} 0%, ${GDIM} 100%)`
              : MU,
            borderRadius: 2,
            transition: "height 0.1s ease",
            animation: isActive ? `wave 0.8s ease infinite ${i * 0.05}s` : "none"
          }}
        />
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIVE CALL CARD
// ═══════════════════════════════════════════════════════════════════════════════

function ActiveCallCard({ call, onJoin, onEnd }) {
  const [duration, setDuration] = useState(0);
  const persona = PERSONA_CONFIG[call.persona] || PERSONA_CONFIG.general_assistant;
  
  useEffect(() => {
    if (call.status === "in_progress" && call.started_at) {
      const startTime = new Date(call.started_at).getTime();
      const interval = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [call.status, call.started_at]);
  
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };
  
  return (
    <div 
      data-testid={`active-call-${call.call_id}`}
      style={{
        padding: 16,
        background: OB3,
        border: `1px solid ${STATUS_COLORS[call.status] || GOLD}40`,
        borderRadius: 12,
        marginBottom: 12
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 44, height: 44,
          borderRadius: 12,
          background: `${STATUS_COLORS[call.status]}20`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          {call.direction === "inbound" 
            ? <PhoneIncoming size={22} color={STATUS_COLORS[call.status]} />
            : <PhoneOutgoing size={22} color={STATUS_COLORS[call.status]} />
          }
        </div>
        
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: WH2, fontSize: 15, fontWeight: 500 }}>
              {call.phone_number}
            </span>
            <span style={{
              padding: "2px 8px",
              background: `${persona.color}20`,
              borderRadius: 10,
              fontSize: 10,
              color: persona.color
            }}>
              {persona.icon} {persona.name}
            </span>
          </div>
          <div style={{ fontSize: 11, color: MU, marginTop: 2 }}>
            {call.direction === "inbound" ? "Inbound" : "Outbound"} • {formatDuration(duration)}
          </div>
        </div>
        
        {/* Status Indicator */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 12px",
          background: `${STATUS_COLORS[call.status]}15`,
          borderRadius: 20
        }}>
          <div style={{
            width: 8, height: 8,
            borderRadius: "50%",
            background: STATUS_COLORS[call.status],
            animation: call.status === "in_progress" ? "pulse 1.5s infinite" : "none"
          }} />
          <span style={{ fontSize: 11, color: STATUS_COLORS[call.status], fontWeight: 500 }}>
            {call.status === "in_progress" ? "LIVE" : call.status.toUpperCase()}
          </span>
        </div>
      </div>
      
      {/* Waveform */}
      <div style={{
        background: OB,
        borderRadius: 8,
        padding: 8,
        marginBottom: 12
      }}>
        <LiveWaveform isActive={call.status === "in_progress"} />
      </div>
      
      {/* Live Transcript Preview */}
      {call.transcript && call.transcript.length > 0 && (
        <div style={{
          background: OB,
          borderRadius: 8,
          padding: 12,
          marginBottom: 12,
          maxHeight: 100,
          overflow: "auto"
        }}>
          {call.transcript.slice(-3).map((entry, i) => (
            <div key={i} style={{ 
              fontSize: 12, 
              color: entry.role === "user" ? WH2 : GOLD2,
              marginBottom: 6,
              display: "flex",
              gap: 8
            }}>
              <span style={{ color: MU, flexShrink: 0 }}>
                [{entry.role === "user" ? "Customer" : "AUREM"}]
              </span>
              <span>{entry.text}</span>
            </div>
          ))}
        </div>
      )}
      
      {/* Action Buttons */}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => onJoin?.(call.call_id)}
          style={{
            flex: 1,
            padding: "10px 16px",
            background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
            border: "none",
            borderRadius: 8,
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
          <Phone size={14} />
          Join Call
        </button>
        <button
          onClick={() => onEnd?.(call.call_id)}
          style={{
            padding: "10px 16px",
            background: "rgba(239,68,68,.1)",
            border: "1px solid rgba(239,68,68,.3)",
            borderRadius: 8,
            color: "#ef4444",
            fontSize: 12,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6
          }}
        >
          <PhoneOff size={14} />
          End
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// OODA TRACE FEED
// ═══════════════════════════════════════════════════════════════════════════════

function OODATraceFeed({ events }) {
  const feedRef = useRef(null);
  
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);
  
  const getPhaseIcon = (phase) => {
    switch (phase) {
      case "observe": return "👁️";
      case "orient": return "🧭";
      case "decide": return "🎯";
      case "act": return "⚡";
      default: return "🔄";
    }
  };
  
  const getPhaseColor = (phase) => {
    switch (phase) {
      case "observe": return "#60a5fa";
      case "orient": return "#a855f7";
      case "decide": return "#f59e0b";
      case "act": return "#4ade80";
      default: return GOLD;
    }
  };
  
  return (
    <div
      ref={feedRef}
      style={{
        height: 300,
        overflow: "auto",
        background: OB,
        borderRadius: 8,
        padding: 12
      }}
    >
      {events.length === 0 ? (
        <div style={{ 
          height: "100%", 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center",
          flexDirection: "column",
          color: MU
        }}>
          <Brain size={32} style={{ marginBottom: 8, opacity: 0.5 }} />
          <span style={{ fontSize: 12 }}>Waiting for call activity...</span>
        </div>
      ) : (
        events.map((event, i) => (
          <div
            key={i}
            style={{
              padding: 10,
              background: OB3,
              borderRadius: 6,
              marginBottom: 8,
              borderLeft: `3px solid ${getPhaseColor(event.phase)}`,
              animation: "fadeIn 0.3s ease"
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span>{getPhaseIcon(event.phase)}</span>
              <span style={{ 
                fontSize: 10, 
                color: getPhaseColor(event.phase),
                fontWeight: 600,
                textTransform: "uppercase"
              }}>
                {event.phase}
              </span>
              <span style={{ fontSize: 9, color: MU, marginLeft: "auto" }}>
                {event.timestamp}
              </span>
            </div>
            <div style={{ fontSize: 12, color: SV }}>
              {event.content}
            </div>
            {event.thought_id && (
              <div style={{ fontSize: 9, color: GDIM, marginTop: 4 }}>
                thought: {event.thought_id}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CALL HISTORY TABLE
// ═══════════════════════════════════════════════════════════════════════════════

function CallHistoryTable({ calls, onSelect }) {
  const formatDuration = (seconds) => {
    if (!seconds) return "—";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };
  
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", { 
      month: "short", 
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };
  
  return (
    <div style={{ 
      background: OB3, 
      border: `1px solid rgba(201,168,76,.1)`, 
      borderRadius: 12,
      overflow: "hidden"
    }}>
      {/* Header */}
      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "1fr 1fr 100px 100px 80px", 
        padding: "12px 16px", 
        borderBottom: `1px solid rgba(201,168,76,.1)`,
        fontSize: 10,
        color: MU,
        letterSpacing: "0.08em"
      }}>
        <div>CALLER</div>
        <div>PERSONA</div>
        <div>DURATION</div>
        <div>STATUS</div>
        <div>TIME</div>
      </div>
      
      {/* Rows */}
      {calls.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: MU }}>
          <Phone size={32} style={{ marginBottom: 8, opacity: 0.3 }} />
          <p style={{ fontSize: 12 }}>No call history yet</p>
        </div>
      ) : (
        calls.map(call => {
          const persona = PERSONA_CONFIG[call.persona] || PERSONA_CONFIG.general_assistant;
          const statusColor = STATUS_COLORS[call.status] || MU;
          
          return (
            <div 
              key={call.call_id}
              onClick={() => onSelect?.(call)}
              data-testid={`call-history-${call.call_id}`}
              style={{ 
                display: "grid", 
                gridTemplateColumns: "1fr 1fr 100px 100px 80px", 
                padding: "14px 16px", 
                borderBottom: `1px solid rgba(201,168,76,.05)`,
                alignItems: "center",
                cursor: "pointer",
                transition: "background 0.15s"
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(201,168,76,.03)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {call.direction === "inbound" 
                  ? <PhoneIncoming size={14} color={GOLD} />
                  : <PhoneOutgoing size={14} color="#60a5fa" />
                }
                <span style={{ color: WH2, fontSize: 13 }}>{call.phone_number}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span>{persona.icon}</span>
                <span style={{ color: SV, fontSize: 12 }}>{persona.name}</span>
              </div>
              <div style={{ color: SV, fontSize: 13, fontFamily: "monospace" }}>
                {formatDuration(call.duration_seconds)}
              </div>
              <div>
                <span style={{
                  padding: "3px 10px",
                  borderRadius: 12,
                  fontSize: 10,
                  background: `${statusColor}15`,
                  color: statusColor
                }}>
                  {call.status}
                </span>
              </div>
              <div style={{ color: MU, fontSize: 11 }}>
                {formatDate(call.started_at)}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// OUTBOUND CALL MODAL
// ═══════════════════════════════════════════════════════════════════════════════

function OutboundCallModal({ isOpen, onClose, onCall, loading }) {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [persona, setPersona] = useState("general_assistant");
  
  if (!isOpen) return null;
  
  const handleCall = () => {
    if (phoneNumber) {
      onCall(phoneNumber, persona);
    }
  };
  
  return (
    <div style={{
      position: "fixed",
      inset: 0,
      background: "rgba(0,0,0,0.7)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000
    }}>
      <div style={{
        background: OB2,
        border: `1px solid ${GOLD}40`,
        borderRadius: 16,
        padding: 24,
        width: 400,
        maxWidth: "90vw"
      }}>
        <h3 style={{ color: GOLD2, fontSize: 18, marginBottom: 20 }}>
          Initiate Outbound Call
        </h3>
        
        {/* Phone Number */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 11, color: MU, marginBottom: 6 }}>
            PHONE NUMBER (E.164 FORMAT)
          </label>
          <input
            type="tel"
            value={phoneNumber}
            onChange={e => setPhoneNumber(e.target.value)}
            placeholder="+1234567890"
            style={{
              width: "100%",
              padding: 12,
              background: OB,
              border: `1px solid rgba(201,168,76,.2)`,
              borderRadius: 8,
              color: WH2,
              fontSize: 14
            }}
          />
        </div>
        
        {/* Persona Selection */}
        <div style={{ marginBottom: 20 }}>
          <label style={{ display: "block", fontSize: 11, color: MU, marginBottom: 8 }}>
            AI PERSONA
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            {Object.entries(PERSONA_CONFIG).map(([key, config]) => (
              <button
                key={key}
                onClick={() => setPersona(key)}
                style={{
                  flex: 1,
                  padding: 12,
                  background: persona === key ? `${config.color}20` : OB,
                  border: `1px solid ${persona === key ? config.color : "rgba(201,168,76,.1)"}`,
                  borderRadius: 8,
                  cursor: "pointer",
                  transition: "all 0.15s"
                }}
              >
                <div style={{ fontSize: 20, marginBottom: 4 }}>{config.icon}</div>
                <div style={{ fontSize: 11, color: persona === key ? config.color : SV }}>
                  {config.name}
                </div>
              </button>
            ))}
          </div>
        </div>
        
        {/* Actions */}
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              padding: 12,
              background: "transparent",
              border: `1px solid rgba(201,168,76,.2)`,
              borderRadius: 8,
              color: SV,
              fontSize: 13,
              cursor: "pointer"
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleCall}
            disabled={!phoneNumber || loading}
            style={{
              flex: 1,
              padding: 12,
              background: phoneNumber ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : OB3,
              border: "none",
              borderRadius: 8,
              color: phoneNumber ? OB : MU,
              fontSize: 13,
              fontWeight: 600,
              cursor: phoneNumber ? "pointer" : "not-allowed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8
            }}
          >
            {loading ? (
              <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
            ) : (
              <>
                <Phone size={16} />
                Call Now
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function VoiceCommand({ businessId }) {
  const [activeCalls, setActiveCalls] = useState([]);
  const [callHistory, setCallHistory] = useState([]);
  const [oodaEvents, setOodaEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOutboundModal, setShowOutboundModal] = useState(false);
  const [callLoading, setCallLoading] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null);
  const [selectedCall, setSelectedCall] = useState(null);
  const wsRef = useRef(null);
  
  // Fetch data
  const fetchData = useCallback(async () => {
    if (!businessId) return;
    
    try {
      // Fetch active calls
      const activeRes = await fetch(`${API_BASE}/api/aurem-voice/${businessId}/calls/active`);
      if (activeRes.ok) {
        const activeData = await activeRes.json();
        setActiveCalls(activeData.active_calls || []);
      }
      
      // Fetch call history
      const historyRes = await fetch(`${API_BASE}/api/aurem-voice/${businessId}/calls?limit=20`);
      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setCallHistory(historyData.calls || []);
      }
      
      // Fetch health status
      const healthRes = await fetch(`${API_BASE}/api/aurem-voice/health`);
      if (healthRes.ok) {
        setHealthStatus(await healthRes.json());
      }
      
    } catch (err) {
      console.error("Failed to fetch voice data:", err);
    } finally {
      setLoading(false);
    }
  }, [businessId]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // WebSocket for real-time updates
  useEffect(() => {
    if (!businessId) return;
    
    const wsUrl = `${API_BASE.replace("http", "ws")}/ws/aurem/${businessId}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "voice_call") {
          // Handle voice call events
          const { call_id, event: callEvent, ...eventData } = data;
          
          if (callEvent === "started") {
            setActiveCalls(prev => [{ call_id, ...eventData, status: "in_progress", transcript: [] }, ...prev]);
          } else if (callEvent === "ended") {
            setActiveCalls(prev => prev.filter(c => c.call_id !== call_id));
            fetchData(); // Refresh history
          } else if (callEvent === "transcript") {
            setActiveCalls(prev => prev.map(c => 
              c.call_id === call_id 
                ? { ...c, transcript: [...(c.transcript || []), { role: eventData.role, text: eventData.text }] }
                : c
            ));
            
            // Add to OODA trace
            if (eventData.thought_id) {
              setOodaEvents(prev => [...prev, {
                phase: "observe",
                content: `User: "${eventData.text}"`,
                thought_id: eventData.thought_id,
                timestamp: new Date().toLocaleTimeString()
              }].slice(-50));
            }
          } else if (callEvent === "tool_call") {
            setOodaEvents(prev => [...prev, {
              phase: "act",
              content: `Executed: ${eventData.function}`,
              timestamp: new Date().toLocaleTimeString()
            }].slice(-50));
          }
        }
      };
      
      ws.onerror = () => {
        console.log("WebSocket connection failed");
      };
      
      return () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch (e) {
      console.log("WebSocket not available");
    }
  }, [businessId, fetchData]);
  
  // Initiate outbound call
  const handleInitiateCall = async (phoneNumber, persona) => {
    setCallLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/aurem-voice/${businessId}/call`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phoneNumber, persona })
      });
      
      const data = await res.json();
      
      if (data.status === "initiated" || data.status === "mock") {
        setShowOutboundModal(false);
        fetchData();
      }
    } catch (err) {
      console.error("Failed to initiate call:", err);
    } finally {
      setCallLoading(false);
    }
  };
  
  // Join/End call handlers (mock for now)
  const handleJoinCall = (callId) => {
    console.log("Join call:", callId);
    // TODO: Implement call transfer/join via Vapi API
  };
  
  const handleEndCall = (callId) => {
    console.log("End call:", callId);
    // TODO: Implement call end via Vapi API
  };
  
  if (loading) {
    return (
      <div style={{ 
        padding: 24, 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "center", 
        minHeight: 400 
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: MU }}>
          <Loader2 size={20} style={{ animation: "spin 1s linear infinite" }} />
          <span>Loading Voice Command Center...</span>
        </div>
      </div>
    );
  }
  
  const isConfigured = healthStatus?.mode === "live";
  
  return (
    <div data-testid="voice-command" style={{ padding: 24 }}>
      {/* Header */}
      <div style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center", 
        marginBottom: 24 
      }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>
            Voice Command Center
          </h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>
            Live operations & AI voice management
          </p>
        </div>
        
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          {/* Configuration Status */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            background: isConfigured ? "rgba(74,222,128,.1)" : "rgba(245,158,11,.1)",
            border: `1px solid ${isConfigured ? "#4ade80" : "#f59e0b"}40`,
            borderRadius: 20,
            fontSize: 11
          }}>
            <div style={{
              width: 6, height: 6,
              borderRadius: "50%",
              background: isConfigured ? "#4ade80" : "#f59e0b"
            }} />
            <span style={{ color: isConfigured ? "#4ade80" : "#f59e0b" }}>
              {isConfigured ? "LIVE" : "NO-KEY MODE"}
            </span>
          </div>
          
          <button
            onClick={() => fetchData()}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: `1px solid rgba(201,168,76,.2)`,
              borderRadius: 8,
              color: GOLD,
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
          
          <button
            onClick={() => setShowOutboundModal(true)}
            data-testid="initiate-call-btn"
            style={{
              padding: "10px 20px",
              background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`,
              border: "none",
              borderRadius: 8,
              color: OB,
              fontWeight: 600,
              fontSize: 12,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6
            }}
          >
            <PhoneOutgoing size={14} />
            New Call
          </button>
        </div>
      </div>
      
      {/* Stats Row */}
      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(4, 1fr)", 
        gap: 16, 
        marginBottom: 24 
      }}>
        {[
          { label: "Active Calls", value: activeCalls.length, icon: PhoneCall, color: "#4ade80" },
          { label: "Today's Calls", value: callHistory.filter(c => {
            const today = new Date().toDateString();
            return new Date(c.started_at).toDateString() === today;
          }).length, icon: Phone, color: GOLD },
          { label: "Avg Duration", value: callHistory.length > 0 
            ? `${Math.round(callHistory.reduce((a, c) => a + (c.duration_seconds || 0), 0) / callHistory.length)}s`
            : "—", icon: Clock, color: "#60a5fa" },
          { label: "Actions Taken", value: callHistory.reduce((a, c) => a + (c.actions_taken?.length || 0), 0), icon: Zap, color: "#a855f7" }
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} style={{ 
            padding: 16, 
            background: OB3, 
            border: `1px solid rgba(201,168,76,.1)`, 
            borderRadius: 12 
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <div style={{
                width: 32, height: 32,
                borderRadius: 8,
                background: `${color}20`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center"
              }}>
                <Icon size={16} color={color} />
              </div>
              <span style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>{label}</span>
            </div>
            <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace" }}>{value}</div>
          </div>
        ))}
      </div>
      
      {/* Main Content Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 20 }}>
        {/* Left Column - Active Calls & History */}
        <div>
          {/* Active Calls */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: 10, 
              marginBottom: 12 
            }}>
              <Activity size={16} color={GOLD} />
              <h3 style={{ color: GOLD2, fontSize: 14, margin: 0, letterSpacing: "0.05em" }}>
                LIVE CALLS
              </h3>
              {activeCalls.length > 0 && (
                <span style={{
                  padding: "2px 8px",
                  background: "rgba(74,222,128,.15)",
                  borderRadius: 10,
                  fontSize: 10,
                  color: "#4ade80",
                  fontWeight: 600
                }}>
                  {activeCalls.length} active
                </span>
              )}
            </div>
            
            {activeCalls.length === 0 ? (
              <div style={{
                padding: 40,
                background: OB3,
                border: `1px solid rgba(201,168,76,.1)`,
                borderRadius: 12,
                textAlign: "center"
              }}>
                <Phone size={32} color={MU} style={{ marginBottom: 8 }} />
                <p style={{ color: MU, fontSize: 13, margin: 0 }}>No active calls</p>
                <p style={{ color: GDIM, fontSize: 11, margin: "4px 0 0" }}>
                  Incoming calls will appear here in real-time
                </p>
              </div>
            ) : (
              activeCalls.map(call => (
                <ActiveCallCard
                  key={call.call_id}
                  call={call}
                  onJoin={handleJoinCall}
                  onEnd={handleEndCall}
                />
              ))
            )}
          </div>
          
          {/* Call History */}
          <div>
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: 10, 
              marginBottom: 12 
            }}>
              <Clock size={16} color={GOLD} />
              <h3 style={{ color: GOLD2, fontSize: 14, margin: 0, letterSpacing: "0.05em" }}>
                CALL HISTORY
              </h3>
            </div>
            <CallHistoryTable 
              calls={callHistory} 
              onSelect={setSelectedCall}
            />
          </div>
        </div>
        
        {/* Right Column - OODA Trace */}
        <div>
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            gap: 10, 
            marginBottom: 12 
          }}>
            <Brain size={16} color={GOLD} />
            <h3 style={{ color: GOLD2, fontSize: 14, margin: 0, letterSpacing: "0.05em" }}>
              OODA TRACE
            </h3>
          </div>
          
          <div style={{
            background: OB3,
            border: `1px solid rgba(201,168,76,.1)`,
            borderRadius: 12,
            padding: 12
          }}>
            <OODATraceFeed events={oodaEvents} />
            
            {/* Legend */}
            <div style={{ 
              display: "flex", 
              gap: 12, 
              marginTop: 12,
              paddingTop: 12,
              borderTop: `1px solid rgba(201,168,76,.1)`
            }}>
              {[
                { phase: "observe", label: "Observe", color: "#60a5fa" },
                { phase: "orient", label: "Orient", color: "#a855f7" },
                { phase: "decide", label: "Decide", color: "#f59e0b" },
                { phase: "act", label: "Act", color: "#4ade80" }
              ].map(({ phase, label, color }) => (
                <div key={phase} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  <span style={{ fontSize: 9, color: MU }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
          
          {/* Persona Quick Reference */}
          <div style={{ marginTop: 16 }}>
            <div style={{ 
              fontSize: 10, 
              color: MU, 
              letterSpacing: "0.08em",
              marginBottom: 8
            }}>
              AVAILABLE PERSONAS
            </div>
            {Object.entries(PERSONA_CONFIG).map(([key, config]) => (
              <div 
                key={key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: 10,
                  background: OB3,
                  borderRadius: 8,
                  marginBottom: 6
                }}
              >
                <span style={{ fontSize: 18 }}>{config.icon}</span>
                <div>
                  <div style={{ fontSize: 12, color: config.color }}>{config.name}</div>
                  <div style={{ fontSize: 10, color: MU }}>{config.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      
      {/* Outbound Call Modal */}
      <OutboundCallModal
        isOpen={showOutboundModal}
        onClose={() => setShowOutboundModal(false)}
        onCall={handleInitiateCall}
        loading={callLoading}
      />
      
      <style>{`
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes wave { 
          0%, 100% { transform: scaleY(0.4); }
          50% { transform: scaleY(1); }
        }
        @keyframes fadeIn { 
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
