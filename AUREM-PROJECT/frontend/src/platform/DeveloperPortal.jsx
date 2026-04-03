import { useState, useEffect, useCallback } from "react";
import { Copy, Check, Key, Shield, Trash2, Plus, Eye, EyeOff, AlertTriangle, Zap, Lock, Code, RefreshCw, Brain } from "lucide-react";
import BrainDebugger from "./BrainDebugger";

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

const SCOPE_DESCRIPTIONS = {
  "chat:read": "Read AI chat completions",
  "chat:write": "Send messages via channels",
  "actions:calendar": "Book/cancel appointments",
  "actions:payments": "Create invoices & payment links",
  "actions:email": "Send emails via Gmail",
  "actions:whatsapp": "Send WhatsApp messages",
  "admin:keys": "Manage API keys",
  "admin:billing": "Access billing dashboard"
};

const BUNDLE_INFO = {
  read_only: { 
    name: "Read Only", 
    desc: "AI chat access only", 
    color: "#60a5fa",
    icon: Eye
  },
  standard: { 
    name: "Standard", 
    desc: "Chat + Email actions", 
    color: "#4ade80",
    icon: Zap
  },
  full_access: { 
    name: "Full Access", 
    desc: "All action capabilities", 
    color: GOLD,
    icon: Shield
  },
  admin: { 
    name: "Admin", 
    desc: "Full access + management", 
    color: "#f87171",
    icon: Lock
  }
};

export default function DeveloperPortal({ businessId }) {
  const [keys, setKeys] = useState([]);
  const [usage, setUsage] = useState(null);
  const [scopeBundles, setScopeBundles] = useState({});
  const [activeTab, setActiveTab] = useState("keys"); // "keys" or "brain"
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKey, setNewKey] = useState(null);
  const [copiedKeyId, setCopiedKeyId] = useState(null);
  const [revokingKeyId, setRevokingKeyId] = useState(null);
  
  // Form state
  const [keyName, setKeyName] = useState("");
  const [isTestKey, setIsTestKey] = useState(false);
  const [selectedBundle, setSelectedBundle] = useState("standard");
  const [rateLimit, setRateLimit] = useState(1000);

  const fetchKeys = useCallback(async () => {
    if (!businessId) return;
    try {
      const res = await fetch(`${API_BASE}/api/aurem-keys/list/${businessId}`);
      const data = await res.json();
      setKeys(data.keys || []);
    } catch (err) {
      console.error("Failed to fetch keys:", err);
    }
  }, [businessId]);

  const fetchUsage = useCallback(async () => {
    if (!businessId) return;
    try {
      const res = await fetch(`${API_BASE}/api/aurem-keys/usage/${businessId}`);
      const data = await res.json();
      setUsage(data);
    } catch (err) {
      console.error("Failed to fetch usage:", err);
    }
  }, [businessId]);

  const fetchScopeBundles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/aurem-keys/scope-bundles`);
      const data = await res.json();
      setScopeBundles(data.bundles || {});
    } catch (err) {
      console.error("Failed to fetch scope bundles:", err);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchKeys(), fetchUsage(), fetchScopeBundles()]);
      setLoading(false);
    };
    loadData();
  }, [fetchKeys, fetchUsage, fetchScopeBundles]);

  const createKey = async () => {
    if (!keyName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/api/aurem-keys/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_id: businessId,
          name: keyName.trim(),
          is_test: isTestKey,
          scope_bundle: selectedBundle,
          rate_limit_daily: rateLimit
        })
      });
      const data = await res.json();
      if (data.api_key) {
        setNewKey(data);
        await fetchKeys();
      }
    } catch (err) {
      console.error("Failed to create key:", err);
    } finally {
      setCreating(false);
    }
  };

  const revokeKey = async (keyId) => {
    setRevokingKeyId(keyId);
    try {
      await fetch(`${API_BASE}/api/aurem-keys/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key_id: keyId, business_id: businessId })
      });
      await fetchKeys();
    } catch (err) {
      console.error("Failed to revoke key:", err);
    } finally {
      setRevokingKeyId(null);
    }
  };

  const copyToClipboard = async (text, keyId) => {
    await navigator.clipboard.writeText(text);
    setCopiedKeyId(keyId);
    setTimeout(() => setCopiedKeyId(null), 2000);
  };

  const resetForm = () => {
    setKeyName("");
    setIsTestKey(false);
    setSelectedBundle("standard");
    setRateLimit(1000);
    setNewKey(null);
    setShowCreateModal(false);
  };

  const activeKeys = keys.filter(k => k.status === "active");
  const revokedKeys = keys.filter(k => k.status === "revoked");

  if (loading) {
    return (
      <div style={{ padding: 24, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: MU }}>
          <RefreshCw size={20} style={{ animation: "spin 1s linear infinite" }} />
          <span>Loading API keys...</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }} data-testid="developer-portal">
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em", display: "flex", alignItems: "center", gap: 10 }}>
            <Key size={22} />
            Developer Portal
          </h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Manage your AUREM API keys and monitor Brain activity</p>
        </div>
        {activeTab === "keys" && (
          <button 
            onClick={() => setShowCreateModal(true)}
            data-testid="create-key-btn"
            style={{ 
              display: "flex", alignItems: "center", gap: 8,
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
            <Plus size={16} />
            Generate New Key
          </button>
        )}
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: `1px solid rgba(201,168,76,.1)`, paddingBottom: 2 }}>
        <button
          onClick={() => setActiveTab("keys")}
          data-testid="tab-keys"
          style={{ 
            padding: "10px 20px",
            background: activeTab === "keys" ? `${GOLD}20` : "transparent",
            border: "none",
            borderBottom: activeTab === "keys" ? `2px solid ${GOLD}` : "2px solid transparent",
            borderRadius: "8px 8px 0 0",
            color: activeTab === "keys" ? GOLD2 : MU,
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8
          }}
        >
          <Key size={14} />
          API Keys
        </button>
        <button
          onClick={() => setActiveTab("brain")}
          data-testid="tab-brain"
          style={{ 
            padding: "10px 20px",
            background: activeTab === "brain" ? `${GOLD}20` : "transparent",
            border: "none",
            borderBottom: activeTab === "brain" ? `2px solid ${GOLD}` : "2px solid transparent",
            borderRadius: "8px 8px 0 0",
            color: activeTab === "brain" ? GOLD2 : MU,
            fontSize: 12,
            fontWeight: 500,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8
          }}
        >
          <Brain size={14} />
          Brain Debugger
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "brain" ? (
        <BrainDebugger />
      ) : (
        <>
      {/* Usage Stats */}
      {usage && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace", marginBottom: 4 }}>
              {usage.total_requests?.toLocaleString() || 0}
            </div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>TOTAL REQUESTS</div>
          </div>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: "#4ade80", fontFamily: "monospace", marginBottom: 4 }}>
              {usage.total_tokens?.toLocaleString() || 0}
            </div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>TOTAL TOKENS</div>
          </div>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: "#60a5fa", fontFamily: "monospace", marginBottom: 4 }}>
              ${usage.estimated_cost_usd?.toFixed(4) || "0.00"}
            </div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>ESTIMATED COST</div>
          </div>
          <div style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: WH2, fontFamily: "monospace", marginBottom: 4 }}>
              {activeKeys.length}
            </div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>ACTIVE KEYS</div>
          </div>
        </div>
      )}

      {/* Active Keys */}
      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, marginBottom: 24, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, display: "flex", alignItems: "center", gap: 8 }}>
          <Shield size={14} color={GOLD} />
          <span style={{ fontSize: 12, color: MU, letterSpacing: "0.08em" }}>ACTIVE API KEYS</span>
          <span style={{ marginLeft: "auto", padding: "2px 8px", background: "rgba(74,222,128,.15)", borderRadius: 10, fontSize: 10, color: "#4ade80" }}>
            {activeKeys.length} active
          </span>
        </div>
        
        {activeKeys.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center" }}>
            <Key size={40} color={GDIM} style={{ marginBottom: 12 }} />
            <p style={{ color: MU, fontSize: 13, margin: 0 }}>No API keys yet. Create your first key to get started.</p>
          </div>
        ) : (
          activeKeys.map(key => (
            <div 
              key={key.key_id} 
              data-testid={`key-row-${key.key_id}`}
              style={{ 
                padding: "16px", 
                borderBottom: `1px solid rgba(201,168,76,.05)`,
                display: "grid",
                gridTemplateColumns: "1fr auto",
                gap: 16,
                alignItems: "center"
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{ color: WH2, fontSize: 14, fontWeight: 500 }}>{key.name}</span>
                  {key.is_test && (
                    <span style={{ padding: "2px 8px", background: "rgba(245,158,11,.15)", borderRadius: 10, fontSize: 9, color: "#f59e0b" }}>
                      TEST
                    </span>
                  )}
                  {key.scope_bundle && BUNDLE_INFO[key.scope_bundle] && (
                    <span style={{ 
                      padding: "2px 8px", 
                      background: `${BUNDLE_INFO[key.scope_bundle].color}20`, 
                      borderRadius: 10, 
                      fontSize: 9, 
                      color: BUNDLE_INFO[key.scope_bundle].color,
                      display: "flex",
                      alignItems: "center",
                      gap: 4
                    }}>
                      {BUNDLE_INFO[key.scope_bundle].name}
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <code style={{ 
                    fontFamily: "monospace", 
                    fontSize: 12, 
                    color: GDIM,
                    background: "rgba(201,168,76,.05)",
                    padding: "4px 8px",
                    borderRadius: 4
                  }}>
                    {key.key_prefix}
                  </code>
                  <button
                    onClick={() => copyToClipboard(key.key_prefix, key.key_id)}
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}
                  >
                    {copiedKeyId === key.key_id ? (
                      <Check size={14} color="#4ade80" />
                    ) : (
                      <Copy size={14} color={MU} />
                    )}
                  </button>
                </div>
                <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 11, color: MU }}>
                  <span>Created: {new Date(key.created_at).toLocaleDateString()}</span>
                  <span>Requests today: <span style={{ color: SV }}>{key.usage_today || 0}</span></span>
                  <span>Rate limit: <span style={{ color: SV }}>{key.rate_limit_daily}/day</span></span>
                </div>
                {key.scopes && key.scopes.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                    {key.scopes.map(scope => (
                      <span 
                        key={scope}
                        style={{ 
                          padding: "2px 6px", 
                          background: "rgba(201,168,76,.08)", 
                          borderRadius: 4, 
                          fontSize: 9, 
                          color: SV 
                        }}
                        title={SCOPE_DESCRIPTIONS[scope]}
                      >
                        {scope}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={() => revokeKey(key.key_id)}
                disabled={revokingKeyId === key.key_id}
                data-testid={`revoke-key-${key.key_id}`}
                style={{ 
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "8px 16px", 
                  background: "rgba(239,68,68,.1)", 
                  border: "1px solid rgba(239,68,68,.3)", 
                  borderRadius: 6, 
                  color: "#ef4444", 
                  fontSize: 11, 
                  cursor: revokingKeyId === key.key_id ? "wait" : "pointer",
                  opacity: revokingKeyId === key.key_id ? 0.5 : 1
                }}
              >
                <Trash2 size={14} />
                Revoke
              </button>
            </div>
          ))
        )}
      </div>

      {/* Revoked Keys (Collapsed) */}
      {revokedKeys.length > 0 && (
        <details style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
          <summary style={{ 
            padding: "12px 16px", 
            cursor: "pointer", 
            display: "flex", 
            alignItems: "center", 
            gap: 8,
            fontSize: 12, 
            color: MU, 
            letterSpacing: "0.08em" 
          }}>
            <AlertTriangle size={14} color="#f87171" />
            REVOKED KEYS ({revokedKeys.length})
          </summary>
          {revokedKeys.map(key => (
            <div 
              key={key.key_id}
              style={{ 
                padding: "12px 16px", 
                borderTop: `1px solid rgba(201,168,76,.05)`,
                opacity: 0.6
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ color: WH2, fontSize: 13, textDecoration: "line-through" }}>{key.name}</span>
                <code style={{ fontFamily: "monospace", fontSize: 11, color: GDIM }}>{key.key_prefix}</code>
              </div>
              <div style={{ fontSize: 10, color: MU, marginTop: 4 }}>
                Revoked: {key.revoked_at ? new Date(key.revoked_at).toLocaleDateString() : "N/A"}
              </div>
            </div>
          ))}
        </details>
      )}

      {/* Quick Start Guide */}
      <div style={{ marginTop: 24, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, padding: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <Code size={16} color={GOLD} />
          <span style={{ fontSize: 12, color: MU, letterSpacing: "0.08em" }}>QUICK START</span>
        </div>
        <pre style={{ 
          background: OB, 
          padding: 16, 
          borderRadius: 8, 
          overflow: "auto", 
          fontSize: 12, 
          color: SV,
          margin: 0
        }}>{`# AUREM LLM Proxy - OpenAI Compatible
curl -X POST ${API_BASE}/api/aurem-llm/chat/completions \\
  -H "Authorization: Bearer sk_aurem_live_xxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello AUREM!"}]
  }'`}</pre>
      </div>
        </>
      )}

      {/* Create Key Modal */}
      {showCreateModal && (
        <div 
          style={{ 
            position: "fixed", 
            inset: 0, 
            background: "rgba(0,0,0,.8)", 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            zIndex: 1000
          }}
          onClick={() => !newKey && resetForm()}
          data-testid="create-key-modal"
        >
          <div 
            style={{ 
              background: OB2, 
              border: `1px solid rgba(201,168,76,.2)`, 
              borderRadius: 16, 
              padding: 24, 
              width: "100%", 
              maxWidth: 500,
              maxHeight: "90vh",
              overflow: "auto"
            }}
            onClick={e => e.stopPropagation()}
          >
            {!newKey ? (
              <>
                <h3 style={{ color: GOLD2, margin: "0 0 20px", fontSize: 18, display: "flex", alignItems: "center", gap: 10 }}>
                  <Key size={20} />
                  Generate New API Key
                </h3>

                {/* Key Name */}
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 11, color: MU, letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>KEY NAME</label>
                  <input
                    type="text"
                    value={keyName}
                    onChange={e => setKeyName(e.target.value)}
                    placeholder="e.g., Production API Key"
                    data-testid="key-name-input"
                    style={{ 
                      width: "100%", 
                      padding: "10px 14px", 
                      background: OB3, 
                      border: `1px solid rgba(201,168,76,.2)`, 
                      borderRadius: 8, 
                      color: WH2, 
                      fontSize: 13,
                      outline: "none"
                    }}
                  />
                </div>

                {/* Environment Toggle */}
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 11, color: MU, letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>ENVIRONMENT</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      onClick={() => setIsTestKey(false)}
                      data-testid="env-live-btn"
                      style={{ 
                        flex: 1, padding: "10px", 
                        background: !isTestKey ? "rgba(74,222,128,.15)" : OB3, 
                        border: `1px solid ${!isTestKey ? "#4ade80" : "rgba(201,168,76,.1)"}`, 
                        borderRadius: 8, 
                        color: !isTestKey ? "#4ade80" : MU, 
                        fontSize: 12, 
                        cursor: "pointer" 
                      }}
                    >
                      Live (sk_aurem_live_)
                    </button>
                    <button
                      onClick={() => setIsTestKey(true)}
                      data-testid="env-test-btn"
                      style={{ 
                        flex: 1, padding: "10px", 
                        background: isTestKey ? "rgba(245,158,11,.15)" : OB3, 
                        border: `1px solid ${isTestKey ? "#f59e0b" : "rgba(201,168,76,.1)"}`, 
                        borderRadius: 8, 
                        color: isTestKey ? "#f59e0b" : MU, 
                        fontSize: 12, 
                        cursor: "pointer" 
                      }}
                    >
                      Test (sk_aurem_test_)
                    </button>
                  </div>
                </div>

                {/* Scope Bundle Selector */}
                <div style={{ marginBottom: 16 }}>
                  <label style={{ fontSize: 11, color: MU, letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>PERMISSION SCOPE</label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {Object.entries(BUNDLE_INFO).map(([key, info]) => {
                      const Icon = info.icon;
                      return (
                        <button
                          key={key}
                          onClick={() => setSelectedBundle(key)}
                          data-testid={`scope-${key}-btn`}
                          style={{ 
                            padding: "12px", 
                            background: selectedBundle === key ? `${info.color}20` : OB3, 
                            border: `1px solid ${selectedBundle === key ? info.color : "rgba(201,168,76,.1)"}`, 
                            borderRadius: 8, 
                            cursor: "pointer",
                            textAlign: "left"
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                            <Icon size={14} color={selectedBundle === key ? info.color : MU} />
                            <span style={{ color: selectedBundle === key ? info.color : WH2, fontSize: 12, fontWeight: 500 }}>
                              {info.name}
                            </span>
                          </div>
                          <div style={{ fontSize: 10, color: MU }}>{info.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Scopes Preview */}
                {scopeBundles[selectedBundle] && (
                  <div style={{ marginBottom: 16, padding: 12, background: "rgba(201,168,76,.05)", borderRadius: 8 }}>
                    <div style={{ fontSize: 10, color: MU, marginBottom: 8 }}>INCLUDED PERMISSIONS:</div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {scopeBundles[selectedBundle].scopes.map(scope => (
                        <span 
                          key={scope}
                          style={{ 
                            padding: "4px 8px", 
                            background: OB3, 
                            borderRadius: 4, 
                            fontSize: 10, 
                            color: SV 
                          }}
                          title={SCOPE_DESCRIPTIONS[scope]}
                        >
                          {scope}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Rate Limit */}
                <div style={{ marginBottom: 24 }}>
                  <label style={{ fontSize: 11, color: MU, letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                    DAILY RATE LIMIT: <span style={{ color: GOLD2 }}>{rateLimit.toLocaleString()}</span> requests/day
                  </label>
                  <input
                    type="range"
                    min={100}
                    max={10000}
                    step={100}
                    value={rateLimit}
                    onChange={e => setRateLimit(parseInt(e.target.value))}
                    data-testid="rate-limit-slider"
                    style={{ width: "100%", accentColor: GOLD }}
                  />
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: MU, marginTop: 4 }}>
                    <span>100</span>
                    <span>10,000</span>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 12 }}>
                  <button
                    onClick={resetForm}
                    style={{ 
                      flex: 1, padding: "12px", 
                      background: "transparent", 
                      border: `1px solid rgba(201,168,76,.2)`, 
                      borderRadius: 8, 
                      color: MU, 
                      fontSize: 13, 
                      cursor: "pointer" 
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={createKey}
                    disabled={!keyName.trim() || creating}
                    data-testid="confirm-create-key-btn"
                    style={{ 
                      flex: 1, padding: "12px", 
                      background: keyName.trim() ? `linear-gradient(135deg, ${GOLD}, ${GDIM})` : OB3, 
                      border: "none", 
                      borderRadius: 8, 
                      color: keyName.trim() ? OB : MU, 
                      fontSize: 13, 
                      fontWeight: 600,
                      cursor: keyName.trim() && !creating ? "pointer" : "not-allowed",
                      opacity: creating ? 0.7 : 1
                    }}
                  >
                    {creating ? "Generating..." : "Generate Key"}
                  </button>
                </div>
              </>
            ) : (
              /* Show New Key */
              <>
                <div style={{ textAlign: "center", marginBottom: 20 }}>
                  <div style={{ 
                    width: 60, height: 60, 
                    background: "rgba(74,222,128,.15)", 
                    borderRadius: "50%", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center",
                    margin: "0 auto 16px"
                  }}>
                    <Check size={30} color="#4ade80" />
                  </div>
                  <h3 style={{ color: GOLD2, margin: 0, fontSize: 18 }}>API Key Created!</h3>
                  <p style={{ color: MU, fontSize: 12, margin: "8px 0 0" }}>
                    Copy your key now. It won't be shown again.
                  </p>
                </div>

                <div style={{ 
                  background: OB3, 
                  border: `1px solid rgba(74,222,128,.3)`, 
                  borderRadius: 8, 
                  padding: 16,
                  marginBottom: 16
                }}>
                  <div style={{ fontSize: 10, color: MU, marginBottom: 8 }}>YOUR API KEY:</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <code 
                      data-testid="new-api-key"
                      style={{ 
                        flex: 1, 
                        fontFamily: "monospace", 
                        fontSize: 13, 
                        color: "#4ade80",
                        wordBreak: "break-all"
                      }}
                    >
                      {newKey.api_key}
                    </code>
                    <button
                      onClick={() => copyToClipboard(newKey.api_key, "new")}
                      data-testid="copy-new-key-btn"
                      style={{ 
                        padding: "8px 12px", 
                        background: copiedKeyId === "new" ? "rgba(74,222,128,.2)" : "rgba(201,168,76,.1)", 
                        border: "none", 
                        borderRadius: 6, 
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        color: copiedKeyId === "new" ? "#4ade80" : GOLD
                      }}
                    >
                      {copiedKeyId === "new" ? <Check size={14} /> : <Copy size={14} />}
                      {copiedKeyId === "new" ? "Copied!" : "Copy"}
                    </button>
                  </div>
                </div>

                <div style={{ 
                  background: "rgba(245,158,11,.1)", 
                  border: "1px solid rgba(245,158,11,.3)", 
                  borderRadius: 8, 
                  padding: 12,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  marginBottom: 20
                }}>
                  <AlertTriangle size={18} color="#f59e0b" style={{ flexShrink: 0, marginTop: 2 }} />
                  <div style={{ fontSize: 12, color: "#f59e0b", lineHeight: 1.5 }}>
                    <strong>Important:</strong> This is the only time you'll see this key. 
                    Store it securely in your environment variables or secrets manager.
                  </div>
                </div>

                <div style={{ fontSize: 11, color: MU, marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span>Name:</span>
                    <span style={{ color: SV }}>{newKey.name}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span>Environment:</span>
                    <span style={{ color: newKey.is_test ? "#f59e0b" : "#4ade80" }}>
                      {newKey.is_test ? "Test" : "Live"}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span>Scope:</span>
                    <span style={{ color: SV }}>{newKey.scope_bundle}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Rate Limit:</span>
                    <span style={{ color: SV }}>{newKey.rate_limit_daily}/day</span>
                  </div>
                </div>

                <button
                  onClick={resetForm}
                  data-testid="done-btn"
                  style={{ 
                    width: "100%", padding: "12px", 
                    background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, 
                    border: "none", 
                    borderRadius: 8, 
                    color: OB, 
                    fontSize: 13, 
                    fontWeight: 600,
                    cursor: "pointer"
                  }}
                >
                  Done
                </button>
              </>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
