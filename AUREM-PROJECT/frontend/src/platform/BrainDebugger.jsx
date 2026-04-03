import { useState, useEffect, useCallback } from "react";
import { Brain, Eye, Compass, Lightbulb, Zap, ChevronDown, ChevronRight, Clock, Target, MessageSquare, RefreshCw, CheckCircle, XCircle, AlertTriangle } from "lucide-react";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

const PHASE_CONFIG = {
  observe: { icon: Eye, color: "#60a5fa", label: "OBSERVE", desc: "Gathering context" },
  orient: { icon: Compass, color: "#f59e0b", label: "ORIENT", desc: "Analyzing intent" },
  decide: { icon: Lightbulb, color: "#a855f7", label: "DECIDE", desc: "Selecting action" },
  act: { icon: Zap, color: "#4ade80", label: "ACT", desc: "Executing" },
  complete: { icon: CheckCircle, color: "#4ade80", label: "COMPLETE", desc: "Done" },
  error: { icon: XCircle, color: "#ef4444", label: "ERROR", desc: "Failed" }
};

const INTENT_COLORS = {
  chat: "#60a5fa",
  book_appointment: "#4ade80",
  check_availability: "#22d3ee",
  send_email: "#f59e0b",
  send_whatsapp: "#25D366",
  create_invoice: "#a855f7",
  create_payment: "#ec4899",
  query_data: "#8b5cf6",
  unknown: "#6b7280"
};

function PhaseCard({ phase, data, isExpanded, onToggle }) {
  const config = PHASE_CONFIG[phase] || PHASE_CONFIG.observe;
  const Icon = config.icon;
  
  if (!data) return null;
  
  return (
    <div style={{ 
      background: OB3, 
      border: `1px solid ${isExpanded ? config.color + '40' : 'rgba(201,168,76,.1)'}`, 
      borderRadius: 8,
      overflow: "hidden",
      transition: "all 0.2s ease"
    }}>
      <button
        onClick={onToggle}
        style={{ 
          width: "100%",
          display: "flex", 
          alignItems: "center", 
          gap: 12,
          padding: "12px 16px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left"
        }}
      >
        <div style={{ 
          width: 36, height: 36, 
          borderRadius: 8, 
          background: `${config.color}20`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          <Icon size={18} color={config.color} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, color: config.color, fontWeight: 600, letterSpacing: "0.05em" }}>
            {config.label}
          </div>
          <div style={{ fontSize: 11, color: MU }}>{config.desc}</div>
        </div>
        {isExpanded ? <ChevronDown size={16} color={MU} /> : <ChevronRight size={16} color={MU} />}
      </button>
      
      {isExpanded && (
        <div style={{ padding: "0 16px 16px", borderTop: `1px solid rgba(201,168,76,.05)` }}>
          {phase === "observe" && <ObserveDetails data={data} />}
          {phase === "orient" && <OrientDetails data={data} />}
          {phase === "decide" && <DecideDetails data={data} />}
          {phase === "act" && <ActDetails data={data} />}
        </div>
      )}
    </div>
  );
}

function ObserveDetails({ data }) {
  return (
    <div style={{ paddingTop: 12 }}>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>USER MESSAGE</div>
        <div style={{ 
          padding: 10, 
          background: OB, 
          borderRadius: 6, 
          fontSize: 13, 
          color: WH2,
          borderLeft: `3px solid ${GOLD}`
        }}>
          "{data.user_message}"
        </div>
      </div>
      
      {data.conversation_history?.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>CONVERSATION HISTORY ({data.conversation_history.length} messages)</div>
          <div style={{ maxHeight: 120, overflow: "auto" }}>
            {data.conversation_history.map((msg, i) => (
              <div key={i} style={{ 
                padding: "6px 10px", 
                background: msg.role === "user" ? "rgba(96,165,250,.1)" : "rgba(74,222,128,.1)",
                borderRadius: 4,
                marginBottom: 4,
                fontSize: 11,
                color: SV
              }}>
                <span style={{ color: msg.role === "user" ? "#60a5fa" : "#4ade80", fontWeight: 500 }}>
                  {msg.role}:
                </span> {msg.content?.substring(0, 100)}{msg.content?.length > 100 ? "..." : ""}
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div style={{ fontSize: 10, color: MU }}>
        <Clock size={10} style={{ display: "inline", marginRight: 4 }} />
        {data.timestamp ? new Date(data.timestamp).toLocaleString() : "N/A"}
      </div>
    </div>
  );
}

function OrientDetails({ data }) {
  const intentColor = INTENT_COLORS[data.intent] || INTENT_COLORS.unknown;
  
  return (
    <div style={{ paddingTop: 12 }}>
      {/* Intent & Confidence */}
      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>INTENT</div>
          <div style={{ 
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "6px 12px",
            background: `${intentColor}20`,
            borderRadius: 20,
            fontSize: 13,
            fontWeight: 600,
            color: intentColor
          }}>
            <Target size={14} />
            {data.intent?.replace(/_/g, " ").toUpperCase()}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>CONFIDENCE</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ 
              width: 80, height: 8, 
              background: OB, 
              borderRadius: 4, 
              overflow: "hidden" 
            }}>
              <div style={{ 
                width: `${(data.confidence || 0) * 100}%`, 
                height: "100%", 
                background: data.confidence > 0.8 ? "#4ade80" : data.confidence > 0.5 ? "#f59e0b" : "#ef4444",
                borderRadius: 4,
                transition: "width 0.3s ease"
              }} />
            </div>
            <span style={{ fontSize: 14, fontFamily: "monospace", color: WH2 }}>
              {((data.confidence || 0) * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
      
      {/* Urgency */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>URGENCY</div>
        <span style={{ 
          padding: "4px 10px",
          borderRadius: 4,
          fontSize: 11,
          fontWeight: 500,
          background: {
            immediate: "rgba(239,68,68,.15)",
            high: "rgba(245,158,11,.15)",
            normal: "rgba(96,165,250,.15)",
            low: "rgba(107,114,128,.15)"
          }[data.urgency] || "rgba(107,114,128,.15)",
          color: {
            immediate: "#ef4444",
            high: "#f59e0b",
            normal: "#60a5fa",
            low: "#6b7280"
          }[data.urgency] || "#6b7280"
        }}>
          {data.urgency?.toUpperCase() || "NORMAL"}
        </span>
      </div>
      
      {/* Extracted Entities */}
      {data.entities && Object.keys(data.entities).filter(k => data.entities[k]).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 8 }}>EXTRACTED ENTITIES</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Object.entries(data.entities).filter(([_, v]) => v).map(([key, value]) => (
              <div key={key} style={{ 
                padding: "6px 10px",
                background: OB,
                borderRadius: 6,
                borderLeft: `2px solid ${GOLD}`
              }}>
                <div style={{ fontSize: 9, color: GDIM, marginBottom: 2 }}>{key.toUpperCase()}</div>
                <div style={{ fontSize: 12, color: WH2 }}>{String(value)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Reasoning */}
      {data.reasoning && (
        <div>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>LLM REASONING</div>
          <div style={{ 
            padding: 10, 
            background: OB, 
            borderRadius: 6, 
            fontSize: 12, 
            color: SV,
            fontStyle: "italic"
          }}>
            "{data.reasoning}"
          </div>
        </div>
      )}
    </div>
  );
}

function DecideDetails({ data }) {
  return (
    <div style={{ paddingTop: 12 }}>
      {/* Selected Tool */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>SELECTED TOOL</div>
        {data.selected_tool ? (
          <div style={{ 
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            background: "rgba(168,85,247,.15)",
            border: "1px solid rgba(168,85,247,.3)",
            borderRadius: 6
          }}>
            <Zap size={14} color="#a855f7" />
            <span style={{ fontSize: 13, color: "#a855f7", fontFamily: "monospace" }}>
              {data.selected_tool}
            </span>
          </div>
        ) : (
          <span style={{ fontSize: 12, color: MU }}>No action tool selected (chat response only)</span>
        )}
      </div>
      
      {/* Tool Parameters */}
      {data.tool_parameters && Object.keys(data.tool_parameters).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>TOOL PARAMETERS</div>
          <pre style={{ 
            padding: 10, 
            background: OB, 
            borderRadius: 6, 
            fontSize: 11, 
            color: SV,
            margin: 0,
            overflow: "auto"
          }}>
            {JSON.stringify(data.tool_parameters, null, 2)}
          </pre>
        </div>
      )}
      
      {/* Decision Reasoning */}
      {data.decision_reasoning && (
        <div>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>DECISION REASONING</div>
          <div style={{ 
            padding: 10, 
            background: OB, 
            borderRadius: 6, 
            fontSize: 12, 
            color: SV 
          }}>
            {data.decision_reasoning}
          </div>
        </div>
      )}
    </div>
  );
}

function ActDetails({ data }) {
  const statusColor = data.action_status === "success" ? "#4ade80" : 
                      data.action_status === "error" ? "#ef4444" : "#f59e0b";
  
  return (
    <div style={{ paddingTop: 12 }}>
      {/* Action Status */}
      {data.action_id && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>ACTION EXECUTED</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <code style={{ 
              padding: "4px 8px", 
              background: OB, 
              borderRadius: 4, 
              fontSize: 11, 
              color: GDIM 
            }}>
              {data.action_id}
            </code>
            <span style={{ 
              padding: "4px 10px",
              borderRadius: 4,
              fontSize: 11,
              fontWeight: 500,
              background: `${statusColor}20`,
              color: statusColor
            }}>
              {data.action_status?.toUpperCase()}
            </span>
          </div>
        </div>
      )}
      
      {/* Action Result */}
      {data.action_result && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>ACTION RESULT</div>
          <pre style={{ 
            padding: 10, 
            background: OB, 
            borderRadius: 6, 
            fontSize: 11, 
            color: SV,
            margin: 0,
            overflow: "auto",
            maxHeight: 150
          }}>
            {JSON.stringify(data.action_result, null, 2)}
          </pre>
        </div>
      )}
      
      {/* Final Response */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 10, color: MU, marginBottom: 4 }}>FINAL RESPONSE</div>
        <div style={{ 
          padding: 12, 
          background: "rgba(74,222,128,.1)", 
          border: "1px solid rgba(74,222,128,.2)",
          borderRadius: 6, 
          fontSize: 13, 
          color: WH2 
        }}>
          {data.final_response}
        </div>
      </div>
      
      {/* WebSocket Push */}
      <div style={{ fontSize: 11, color: data.pushed_to_dashboard ? "#4ade80" : MU }}>
        {data.pushed_to_dashboard ? (
          <>
            <CheckCircle size={12} style={{ display: "inline", marginRight: 4 }} />
            Pushed to dashboard via WebSocket
          </>
        ) : (
          <>
            <AlertTriangle size={12} style={{ display: "inline", marginRight: 4 }} />
            Not pushed to dashboard
          </>
        )}
      </div>
    </div>
  );
}

function ThoughtCard({ thought, isSelected, onSelect }) {
  const statusConfig = PHASE_CONFIG[thought.status] || PHASE_CONFIG.complete;
  const StatusIcon = statusConfig.icon;
  const orient = thought.phases?.orient || thought.orient;
  const intentColor = INTENT_COLORS[orient?.intent] || INTENT_COLORS.unknown;
  
  return (
    <button
      onClick={onSelect}
      data-testid={`thought-${thought.thought_id}`}
      style={{ 
        width: "100%",
        padding: 12,
        background: isSelected ? `${GOLD}15` : OB3,
        border: `1px solid ${isSelected ? GOLD : 'rgba(201,168,76,.1)'}`,
        borderRadius: 8,
        cursor: "pointer",
        textAlign: "left",
        transition: "all 0.15s ease"
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div style={{ fontSize: 10, color: GDIM, fontFamily: "monospace" }}>
          {thought.thought_id}
        </div>
        <StatusIcon size={14} color={statusConfig.color} />
      </div>
      
      {orient?.intent && (
        <div style={{ 
          display: "inline-block",
          padding: "3px 8px",
          background: `${intentColor}20`,
          borderRadius: 12,
          fontSize: 10,
          fontWeight: 500,
          color: intentColor,
          marginBottom: 8
        }}>
          {orient.intent.replace(/_/g, " ")}
        </div>
      )}
      
      <div style={{ fontSize: 12, color: SV, marginBottom: 6, lineHeight: 1.4 }}>
        {thought.input?.message?.substring(0, 60)}{thought.input?.message?.length > 60 ? "..." : ""}
      </div>
      
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: MU }}>
        <span>{thought.started_at ? new Date(thought.started_at).toLocaleTimeString() : ""}</span>
        <span>{thought.duration_ms ? `${thought.duration_ms}ms` : ""}</span>
      </div>
    </button>
  );
}

export default function BrainDebugger() {
  const [thoughts, setThoughts] = useState([]);
  const [selectedThought, setSelectedThought] = useState(null);
  const [expandedPhases, setExpandedPhases] = useState(["observe", "orient", "decide", "act"]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authError, setAuthError] = useState("");
  
  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('platform_token');
    if (token) {
      setIsAuthenticated(true);
      // Auto-load thoughts for authenticated users
      fetchThoughts(token);
    }
  }, []);
  
  const fetchThoughts = useCallback(async (token) => {
    const authToken = token || localStorage.getItem('platform_token');
    if (!authToken) {
      setAuthError("Please login to access Brain Debugger");
      return;
    }
    
    setLoading(true);
    setAuthError("");
    
    try {
      // Fetch brain thoughts for admin
      const res = await fetch(`${API_BASE}/api/brain/admin/thoughts?limit=20`, {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      
      if (res.status === 401 || res.status === 403) {
        setAuthError("Session expired. Please login again.");
        setIsAuthenticated(false);
        return;
      }
      
      if (res.ok) {
        const data = await res.json();
        setThoughts(data.thoughts || data || []);
        if ((data.thoughts?.length > 0 || data?.length > 0) && !selectedThought) {
          setSelectedThought(data.thoughts?.[0] || data[0]);
        }
      } else {
        // If admin endpoint doesn't exist, show demo data
        setThoughts(getDemoThoughts());
        setSelectedThought(getDemoThoughts()[0]);
      }
    } catch (err) {
      console.error("Failed to fetch thoughts:", err);
      // Show demo data on error
      setThoughts(getDemoThoughts());
      setSelectedThought(getDemoThoughts()[0]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedThought]);
  
  const getDemoThoughts = () => [{
    thought_id: "thought_demo_001",
    status: "complete",
    started_at: new Date().toISOString(),
    duration_ms: 1250,
    input: { message: "What automation strategies can help my skincare business?" },
    phases: {
      observe: {
        user_message: "What automation strategies can help my skincare business?",
        conversation_history: [],
        timestamp: new Date().toISOString()
      },
      orient: {
        intent: "chat",
        confidence: 0.95,
        urgency: "normal",
        entities: { business_type: "skincare", topic: "automation" },
        reasoning: "User is asking for business advice about automation in skincare industry"
      },
      decide: {
        selected_tool: null,
        tool_parameters: {},
        decision_reasoning: "This is a general knowledge question - provide comprehensive chat response"
      },
      act: {
        action_status: "success",
        final_response: "For your skincare business, I recommend focusing on inventory automation, customer follow-up sequences, and appointment scheduling systems.",
        pushed_to_dashboard: true
      }
    }
  }, {
    thought_id: "thought_demo_002",
    status: "complete",
    started_at: new Date(Date.now() - 300000).toISOString(),
    duration_ms: 890,
    input: { message: "Send a promotional email to my VIP customers" },
    phases: {
      observe: {
        user_message: "Send a promotional email to my VIP customers",
        conversation_history: [],
        timestamp: new Date(Date.now() - 300000).toISOString()
      },
      orient: {
        intent: "send_email",
        confidence: 0.92,
        urgency: "normal",
        entities: { action: "send_email", segment: "VIP customers", type: "promotional" },
        reasoning: "User wants to send marketing email to a specific customer segment"
      },
      decide: {
        selected_tool: "email_campaign_tool",
        tool_parameters: { segment: "vip", template: "promotional" },
        decision_reasoning: "Using email campaign tool with VIP segment filter"
      },
      act: {
        action_id: "email_123",
        action_status: "success",
        action_result: { sent: 47, failed: 0 },
        final_response: "Successfully sent promotional email to 47 VIP customers.",
        pushed_to_dashboard: true
      }
    }
  }];
  
  const togglePhase = (phase) => {
    setExpandedPhases(prev => 
      prev.includes(phase) ? prev.filter(p => p !== phase) : [...prev, phase]
    );
  };
  
  const handleRefresh = () => {
    setRefreshing(true);
    fetchThoughts();
  };
  
  // Show loading state
  if (loading && thoughts.length === 0) {
    return (
      <div data-testid="brain-debugger" style={{ padding: 24 }}>
        <div style={{ 
          maxWidth: 500, 
          margin: "0 auto", 
          textAlign: "center",
          padding: 40,
          background: OB3,
          border: "1px solid rgba(201,168,76,.1)",
          borderRadius: 12
        }}>
          <Brain size={48} color={GOLD} style={{ marginBottom: 16, animation: "pulse 1.5s infinite" }} />
          <h3 style={{ color: GOLD2, fontSize: 18, margin: "0 0 8px" }}>Loading Brain Activity</h3>
          <p style={{ color: MU, fontSize: 13 }}>
            Fetching OODA loop execution details...
          </p>
        </div>
        <style>{`
          @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        `}</style>
      </div>
    );
  }
  
  // Show auth error if not authenticated
  if (authError && !isAuthenticated) {
    return (
      <div data-testid="brain-debugger" style={{ padding: 24 }}>
        <div style={{ 
          maxWidth: 500, 
          margin: "0 auto", 
          textAlign: "center",
          padding: 40,
          background: OB3,
          border: "1px solid rgba(239,68,68,.2)",
          borderRadius: 12
        }}>
          <Brain size={48} color="#ef4444" style={{ marginBottom: 16 }} />
          <h3 style={{ color: "#ef4444", fontSize: 18, margin: "0 0 8px" }}>Authentication Required</h3>
          <p style={{ color: MU, fontSize: 13, marginBottom: 24 }}>
            {authError}
          </p>
          <a 
            href="/platform/login"
            style={{ 
              display: "inline-block",
              padding: "12px 24px", 
              background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, 
              border: "none", 
              borderRadius: 8, 
              color: OB, 
              fontWeight: 600, 
              textDecoration: "none",
              fontSize: 13
            }}
          >
            Login to Continue
          </a>
        </div>
      </div>
    );
  }
  
  return (
    <div data-testid="brain-debugger" style={{ display: "flex", gap: 20, height: "calc(100vh - 200px)", minHeight: 500 }}>
      {/* Thought List */}
      <div style={{ width: 280, flexShrink: 0, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ color: GOLD2, fontSize: 14, margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <Brain size={16} />
            Recent Thoughts
          </h3>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{ 
              background: "transparent", 
              border: "none", 
              cursor: refreshing ? "wait" : "pointer",
              padding: 4
            }}
          >
            <RefreshCw size={14} color={MU} style={{ animation: refreshing ? "spin 1s linear infinite" : "none" }} />
          </button>
        </div>
        
        <div style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
          {thoughts.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", color: MU, fontSize: 12 }}>
              No thoughts yet. Send a message via the Brain API to see activity.
            </div>
          ) : (
            thoughts.map(thought => (
              <ThoughtCard
                key={thought.thought_id}
                thought={thought}
                isSelected={selectedThought?.thought_id === thought.thought_id}
                onSelect={() => setSelectedThought(thought)}
              />
            ))
          )}
        </div>
      </div>
      
      {/* Thought Detail */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {selectedThought ? (
          <>
            {/* Header */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                <h3 style={{ color: GOLD2, fontSize: 16, margin: 0 }}>OODA Loop Inspector</h3>
                <span style={{ 
                  padding: "4px 10px",
                  background: PHASE_CONFIG[selectedThought.status]?.color + "20",
                  borderRadius: 12,
                  fontSize: 10,
                  fontWeight: 600,
                  color: PHASE_CONFIG[selectedThought.status]?.color
                }}>
                  {selectedThought.status?.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: 11, color: MU }}>
                <code style={{ color: GDIM }}>{selectedThought.thought_id}</code>
                <span style={{ margin: "0 8px" }}>•</span>
                {selectedThought.duration_ms}ms total
                <span style={{ margin: "0 8px" }}>•</span>
                {selectedThought.started_at ? new Date(selectedThought.started_at).toLocaleString() : ""}
              </div>
            </div>
            
            {/* OODA Timeline */}
            <div style={{ 
              display: "flex", 
              alignItems: "center", 
              gap: 4, 
              marginBottom: 20,
              padding: 12,
              background: OB3,
              borderRadius: 8
            }}>
              {["observe", "orient", "decide", "act"].map((phase, i) => {
                const config = PHASE_CONFIG[phase];
                const Icon = config.icon;
                const isComplete = selectedThought.phases?.[phase] || selectedThought[phase];
                
                return (
                  <div key={phase} style={{ display: "flex", alignItems: "center", flex: 1 }}>
                    <div style={{ 
                      display: "flex", 
                      flexDirection: "column", 
                      alignItems: "center",
                      flex: 1
                    }}>
                      <div style={{ 
                        width: 32, height: 32, 
                        borderRadius: "50%", 
                        background: isComplete ? `${config.color}30` : OB,
                        border: `2px solid ${isComplete ? config.color : MU}`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        marginBottom: 4
                      }}>
                        <Icon size={14} color={isComplete ? config.color : MU} />
                      </div>
                      <span style={{ fontSize: 9, color: isComplete ? config.color : MU, fontWeight: 500 }}>
                        {config.label}
                      </span>
                    </div>
                    {i < 3 && (
                      <div style={{ 
                        flex: 1, 
                        height: 2, 
                        background: isComplete ? config.color : "rgba(201,168,76,.1)",
                        marginTop: -16
                      }} />
                    )}
                  </div>
                );
              })}
            </div>
            
            {/* Phase Cards */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {["observe", "orient", "decide", "act"].map(phase => (
                <PhaseCard
                  key={phase}
                  phase={phase}
                  data={selectedThought.phases?.[phase] || selectedThought[phase]}
                  isExpanded={expandedPhases.includes(phase)}
                  onToggle={() => togglePhase(phase)}
                />
              ))}
            </div>
          </>
        ) : (
          <div style={{ 
            display: "flex", 
            flexDirection: "column", 
            alignItems: "center", 
            justifyContent: "center",
            height: "100%",
            color: MU
          }}>
            <MessageSquare size={40} style={{ marginBottom: 12 }} />
            <p style={{ fontSize: 13 }}>Select a thought to inspect</p>
          </div>
        )}
      </div>
      
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
