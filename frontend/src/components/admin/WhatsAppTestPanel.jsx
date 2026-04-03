/**
 * WhatsAppTestPanel.jsx
 * ─────────────────────────────────────────────────────
 * WhatsApp AI Test Console for Admin Dashboard
 * Tests intent detection, live data fetching, and AI replies
 * ─────────────────────────────────────────────────────
 */

import { useState, useRef, useEffect } from "react";

// ── QUICK-FIRE TEST MESSAGES ─────────────────────────────────────────────────
const QUICK_MSGS = [
  "Do you have the ARC serum in stock?",
  "Where is my order RR-1042?",
  "What ingredients are in the ACRC cream?",
  "How much is shipping to Vancouver?",
  "How much does the combo cost?",
  "Is the AURA-GEN combo safe for sensitive skin?",
  "What's the difference between ARC and ACRC?",
  "Do you ship to the US?",
];

const INTENT_COLORS = {
  stock_check:    { bg: "#e8f5e9", color: "#2e7d32", label: "Stock Check" },
  order_status:   { bg: "#e3f2fd", color: "#1565c0", label: "Order Status" },
  ingredients:    { bg: "#f3e5f5", color: "#6a1b9a", label: "Ingredients" },
  shipping_rate:  { bg: "#fff3e0", color: "#e65100", label: "Shipping" },
  product_info:   { bg: "#fce4ec", color: "#880e4f", label: "Product Info" },
  general:        { bg: "#f5f5f5", color: "#424242", label: "General" },
};

// ── MOCK ENGINE (runs entirely client-side — fallback when backend unavailable) ────
function mockDetectIntent(msg) {
  const m = msg.toLowerCase();
  if (/order|track|ship|deliver|where is|status/.test(m))   return "order_status";
  if (/stock|available|do you have|out of/.test(m))          return "stock_check";
  if (/ingredient|what's in|formula|retinal|arbutin|contain/.test(m)) return "ingredients";
  if (/shipping|how much to ship|ship to|delivery cost/.test(m))      return "shipping_rate";
  if (/price|how much|combo|bundle|cost|aura-gen|arc|acrc/.test(m))   return "product_info";
  return "general";
}

const MOCK_LIVE_DATA = {
  stock_check:   "AURA-GEN Combo (ACRC + ARC): CAD $149 — Stock: 48 units\nACRC Rich Cream 35mL: CAD $89 — Stock: 60\nARC Active Recovery Serum 30mL: CAD $79 — Stock: 55",
  order_status:  "Order RR-1042 — Status: Shipped\nCarrier: FlagShip / Canada Post\nTracking: 1234567890\nEstimated delivery: 2–3 business days",
  ingredients:   "ACRC Rich Cream: Retinal (Encapsulated) 0.5% net, Bakuchiol 1%, Peptide Complex, Niacinamide 5%, Ceramides, Hyaluronic Acid\nARC Serum: Alpha Arbutin 3%, Tranexamic Acid 3%, Vitamin C MAP 10%, Niacinamide 4%",
  shipping_rate: "Canada: Calculated at checkout via FlagShip. Est. $8–14 CAD standard.\nFree shipping on orders over $99 CAD.\nUS shipping: not available yet.",
  product_info:  "AURA-GEN Combo (ACRC Rich Cream + ARC Serum): CAD $149 — sold as combo only.\nACRC Rich Cream 35mL: CAD $89\nARC Active Recovery Serum 30mL: CAD $79",
  general:       null,
};

const MOCK_REPLIES = {
  stock_check:   () => "Yes! The AURA-GEN combo (ACRC Rich Cream + ARC Serum) is in stock at CAD $149 — that's 48 units available right now. You can order at reroots.ca",
  order_status:  () => "Your order RR-1042 has shipped! It's on its way via Canada Post — tracking number 1234567890. Estimated delivery is 2–3 business days.",
  ingredients:   () => "The ACRC Rich Cream contains Encapsulated Retinal (0.5% net), Bakuchiol 1%, Peptide Complex, Niacinamide 5%, Ceramides, and Hyaluronic Acid. All formulations are fragrance-free and paraben-free.",
  shipping_rate: () => "We ship across Canada via FlagShip — rates are calculated at checkout based on your postal code, typically $8–14 CAD for standard delivery. Free shipping on orders over $99!",
  product_info:  () => "The AURA-GEN combo (ACRC Rich Cream + ARC Serum) is CAD $149 and is sold as a set only — the two products are designed to work together as a complete system.",
  general:       () => "Great question! AURA-GEN is ReRoots' precision biotech skincare line — two products formulated to work together: the ACRC Rich Cream (nightly recovery) and ARC Serum (active brightening + repair).",
};

async function mockApiCall(message) {
  await new Promise(r => setTimeout(r, 900 + Math.random() * 600));
  const intent   = mockDetectIntent(message);
  const liveData = MOCK_LIVE_DATA[intent];
  const reply    = MOCK_REPLIES[intent]?.() ?? MOCK_REPLIES.general();
  const orderMatch = message.match(/rr[-#]?(\d{3,6})/i);

  return {
    intent,
    extracted_value: orderMatch ? orderMatch[0].toUpperCase() : null,
    fetch_url: liveData
      ? intent === "stock_check"   ? "https://reroots.ca/api/products"
      : intent === "order_status"  ? `https://reroots.ca/api/orders/track/${orderMatch?.[0] ?? "?"}`
      : intent === "ingredients"   ? "https://reroots.ca/ingredients"
      : intent === "shipping_rate" ? "https://reroots.ca/shipping"
      : intent === "product_info"  ? "https://reroots.ca/api/products"
      : null
      : null,
    live_data: liveData,
    reply,
    latency_ms: Math.floor(900 + Math.random() * 600),
    browser_used: false,
    fallback_used: !!liveData,
    mock: true,
  };
}

// ── STYLES ────────────────────────────────────────────────────────────────────
const S = {
  wrap: {
    fontFamily: "'IBM Plex Mono', 'Fira Mono', 'SF Mono', monospace",
    background: "#0d1117",
    color: "#e6edf3",
    minHeight: "100%",
    padding: "24px",
    fontSize: "13px",
    borderRadius: "12px",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    marginBottom: "20px",
    paddingBottom: "16px",
    borderBottom: "1px solid #21262d",
  },
  title: {
    fontSize: "16px", fontWeight: 600, color: "#e6edf3",
    letterSpacing: "0.02em",
    display: "flex", alignItems: "center", gap: "10px",
  },
  badge: (color) => ({
    fontSize: "10px", fontWeight: 500, letterSpacing: "0.08em",
    background: color + "22", color, border: `1px solid ${color}44`,
    borderRadius: "4px", padding: "3px 10px", textTransform: "uppercase",
  }),
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "20px",
    minHeight: "600px",
  },
  panel: {
    background: "#161b22",
    border: "1px solid #21262d",
    borderRadius: "8px",
    display: "flex", flexDirection: "column",
    overflow: "hidden",
  },
  panelHead: {
    padding: "14px 18px",
    borderBottom: "1px solid #21262d",
    fontSize: "11px", fontWeight: 600, letterSpacing: "0.1em",
    textTransform: "uppercase", color: "#8b949e",
    display: "flex", alignItems: "center", justifyContent: "space-between",
  },
  chatArea: {
    flex: 1, overflowY: "auto", padding: "18px",
    display: "flex", flexDirection: "column", gap: "14px",
    maxHeight: "450px",
  },
  inputRow: {
    padding: "14px 16px",
    borderTop: "1px solid #21262d",
    display: "flex", gap: "10px",
  },
  input: {
    flex: 1, background: "#0d1117",
    border: "1px solid #30363d", borderRadius: "6px",
    padding: "10px 14px", color: "#e6edf3",
    fontFamily: "inherit", fontSize: "13px",
    outline: "none",
  },
  sendBtn: (loading) => ({
    background: loading ? "#21262d" : "#238636",
    color: loading ? "#8b949e" : "#fff",
    border: "none", borderRadius: "6px",
    padding: "10px 20px", cursor: loading ? "not-allowed" : "pointer",
    fontSize: "12px", fontWeight: 600, letterSpacing: "0.05em",
    transition: "all .2s", whiteSpace: "nowrap",
    fontFamily: "inherit",
  }),
  bubble: (role) => ({
    maxWidth: "85%",
    alignSelf: role === "user" ? "flex-end" : "flex-start",
    background: role === "user" ? "#1f6feb" : "#21262d",
    color: "#e6edf3",
    borderRadius: role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
    padding: "12px 16px",
    fontSize: "13px", lineHeight: "1.6",
  }),
  waLabel: {
    fontSize: "10px", color: "#8b949e", marginBottom: "5px",
    letterSpacing: "0.08em", textTransform: "uppercase",
  },
  debugPanel: {
    flex: 1, overflowY: "auto", padding: "16px 18px",
    display: "flex", flexDirection: "column", gap: "16px",
    maxHeight: "550px",
  },
  debugBlock: {
    background: "#0d1117",
    border: "1px solid #21262d",
    borderRadius: "6px",
    overflow: "hidden",
  },
  debugBlockHead: {
    padding: "8px 14px",
    background: "#161b22",
    borderBottom: "1px solid #21262d",
    fontSize: "10px", fontWeight: 600, letterSpacing: "0.1em",
    textTransform: "uppercase", color: "#8b949e",
    display: "flex", alignItems: "center", gap: "8px",
  },
  debugBlockBody: {
    padding: "12px 14px",
    fontSize: "12px", lineHeight: "1.7",
    color: "#c9d1d9", whiteSpace: "pre-wrap", wordBreak: "break-word",
  },
  quickWrap: {
    display: "flex", flexWrap: "wrap", gap: "8px",
    padding: "12px 16px",
    borderBottom: "1px solid #21262d",
  },
  quickBtn: {
    fontSize: "11px", background: "#21262d",
    color: "#8b949e", border: "1px solid #30363d",
    borderRadius: "4px", padding: "6px 12px",
    cursor: "pointer", transition: "all .2s", fontFamily: "inherit",
  },
  dot: (color) => ({
    width: "8px", height: "8px", borderRadius: "50%",
    background: color, display: "inline-block", flexShrink: 0,
  }),
  latency: {
    fontSize: "10px", color: "#57ab5a", letterSpacing: "0.06em",
  },
  emptyState: {
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center",
    color: "#484f58", gap: "10px", textAlign: "center",
    padding: "40px",
  },
};

// ── TYPING INDICATOR ─────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div style={{ display: "flex", gap: "5px", padding: "4px 2px" }}>
      {[0,1,2].map(i => (
        <span key={i} style={{
          width: "7px", height: "7px", borderRadius: "50%",
          background: "#58a6ff", display: "inline-block",
          animation: `typingPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
        }} />
      ))}
    </div>
  );
}

// ── DEBUG ENTRY ───────────────────────────────────────────────────────────────
function DebugEntry({ entry }) {
  const ic = INTENT_COLORS[entry.intent] ?? INTENT_COLORS.general;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>

      {/* Intent */}
      <div style={S.debugBlock}>
        <div style={S.debugBlockHead}>
          <span style={S.dot("#58a6ff")} /> Intent Detection
          <span style={{ marginLeft: "auto", ...S.latency }}>{entry.latency_ms}ms</span>
        </div>
        <div style={S.debugBlockBody}>
          <span style={S.badge(ic.color)}>{ic.label}</span>
          {entry.extracted_value && (
            <span style={{ marginLeft: "12px", color: "#e3b341", fontWeight: 500 }}>
              extracted: {entry.extracted_value}
            </span>
          )}
          {entry.mock && (
            <span style={{ marginLeft: "12px", color: "#f85149", fontSize: "10px" }}>
              (MOCK - backend unavailable)
            </span>
          )}
        </div>
      </div>

      {/* Fetch URL */}
      {entry.fetch_url && (
        <div style={S.debugBlock}>
          <div style={S.debugBlockHead}>
            <span style={S.dot("#57ab5a")} /> Browser Fetch
            <span style={{ marginLeft: "auto", fontSize: "10px", color: entry.browser_used ? "#57ab5a" : "#e3b341" }}>
              {entry.browser_used ? "PinchTab" : "httpx fallback"}
            </span>
          </div>
          <div style={{ ...S.debugBlockBody, color: "#79c0ff", fontFamily: "monospace" }}>
            GET {entry.fetch_url}
          </div>
        </div>
      )}

      {/* Live Data */}
      {entry.live_data && (
        <div style={S.debugBlock}>
          <div style={S.debugBlockHead}>
            <span style={S.dot("#57ab5a")} /> Live Data Injected
          </div>
          <div style={S.debugBlockBody}>{entry.live_data}</div>
        </div>
      )}

      {!entry.fetch_url && (
        <div style={S.debugBlock}>
          <div style={S.debugBlockHead}>
            <span style={S.dot("#484f58")} /> No Browse Needed
          </div>
          <div style={{ ...S.debugBlockBody, color: "#484f58" }}>
            Answered from AI knowledge base only.
          </div>
        </div>
      )}

      {/* LLM Reply */}
      <div style={S.debugBlock}>
        <div style={S.debugBlockHead}>
          <span style={S.dot("#bc8cff")} /> LLM Reply Sent
        </div>
        <div style={S.debugBlockBody}>{entry.reply}</div>
      </div>
    </div>
  );
}

// ── MAIN COMPONENT ────────────────────────────────────────────────────────────
export default function WhatsAppTestPanel() {
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [debugLog, setDebugLog] = useState([]);
  const chatEndRef  = useRef(null);
  const debugEndRef = useRef(null);
  const inputRef    = useRef(null);

  const API = (window.location.hostname.includes('reroots.ca') 
    ? 'https://reroots.ca' 
    : process.env.REACT_APP_BACKEND_URL) || '';

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    debugEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [debugLog]);

  const clearAll = () => { setMessages([]); setDebugLog([]); };

  const send = async (text) => {
    const msg = text ?? input.trim();
    if (!msg || loading) return;
    setInput("");
    setLoading(true);

    setMessages(prev => [...prev, { role: "user", text: msg }]);

    // Try real backend first, fall back to mock
    let data;
    try {
      const token = localStorage.getItem('reroots_token');
      const res = await fetch(`${API}/api/admin/whatsapp/test`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { "Authorization": `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ message: msg, customer_name: "Admin Test" }),
      });
      if (!res.ok) throw new Error("backend unavailable");
      data = await res.json();
    } catch {
      data = await mockApiCall(msg);
    }

    setMessages(prev => [...prev, { role: "bot", text: data.reply }]);
    setDebugLog(prev => [...prev, { ...data, message: msg }]);
    setLoading(false);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        .wa-test-panel * { box-sizing: border-box; }
        .wa-test-panel ::-webkit-scrollbar { width: 6px; }
        .wa-test-panel ::-webkit-scrollbar-track { background: transparent; }
        .wa-test-panel ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
        @keyframes typingPulse {
          0%, 100% { opacity: .3; transform: scale(.8); }
          50%       { opacity: 1;  transform: scale(1.1); }
        }
        .wa-quick-btn:hover { background: #30363d !important; color: #e6edf3 !important; border-color: #58a6ff !important; }
      `}</style>

      <div className="wa-test-panel" style={S.wrap} data-testid="whatsapp-test-panel">

        {/* HEADER */}
        <div style={S.header}>
          <div style={S.title}>
            <span style={{ fontSize: "20px" }}>💬</span> 
            WhatsApp AI Test Console
            <span style={S.badge("#57ab5a")}>Live</span>
          </div>
          <button
            onClick={clearAll}
            className="wa-quick-btn"
            style={{ ...S.quickBtn, padding: "8px 16px" }}
          >
            Clear All
          </button>
        </div>

        {/* MAIN GRID */}
        <div style={S.grid}>

          {/* LEFT — CHAT SIMULATOR */}
          <div style={S.panel}>
            <div style={S.panelHead}>
              <span>WhatsApp Simulator</span>
              <span style={{ color: "#57ab5a", fontSize: "11px" }}>ReRoots Bot</span>
            </div>

            {/* Quick fire buttons */}
            <div style={S.quickWrap}>
              {QUICK_MSGS.map(m => (
                <button
                  key={m}
                  className="wa-quick-btn"
                  style={S.quickBtn}
                  onClick={() => send(m)}
                  disabled={loading}
                >
                  {m.length > 35 ? m.slice(0, 33) + "…" : m}
                </button>
              ))}
            </div>

            {/* Chat bubbles */}
            <div style={S.chatArea}>
              {messages.length === 0 && (
                <div style={S.emptyState}>
                  <span style={{ fontSize: "32px" }}>💬</span>
                  <span style={{ fontWeight: 500 }}>WhatsApp Chat Simulator</span>
                  <span style={{ fontSize: "12px", color: "#6e7681" }}>
                    Type a message or pick a quick test above
                  </span>
                </div>
              )}
              {messages.map((m, i) => (
                <div key={i} style={{ display: "flex", flexDirection: "column",
                  alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
                  <div style={S.waLabel}>{m.role === "user" ? "You (Admin)" : "ReRoots Bot"}</div>
                  <div style={S.bubble(m.role)}>{m.text}</div>
                </div>
              ))}
              {loading && (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
                  <div style={S.waLabel}>ReRoots Bot</div>
                  <div style={{ ...S.bubble("bot"), padding: "12px 18px" }}>
                    <TypingDots />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div style={S.inputRow}>
              <input
                ref={inputRef}
                style={S.input}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Type a customer message…"
                disabled={loading}
              />
              <button
                style={S.sendBtn(loading)}
                onClick={() => send()}
                disabled={loading}
              >
                {loading ? "..." : "Send"}
              </button>
            </div>
          </div>

          {/* RIGHT — DEBUG OUTPUT */}
          <div style={S.panel}>
            <div style={S.panelHead}>
              <span>Debug Pipeline</span>
              <span style={{ color: "#6e7681" }}>
                {debugLog.length} {debugLog.length === 1 ? "test" : "tests"}
              </span>
            </div>

            <div style={S.debugPanel}>
              {debugLog.length === 0 && (
                <div style={S.emptyState}>
                  <span style={{ fontSize: "32px" }}>🔍</span>
                  <span style={{ fontWeight: 500 }}>Debug Output</span>
                  <span style={{ fontSize: "12px", color: "#6e7681", maxWidth: "260px" }}>
                    Shows: Intent Detection → Fetch URL → Live Data → LLM Reply
                  </span>
                </div>
              )}
              {debugLog.map((entry, i) => (
                <div key={i}>
                  <div style={{
                    fontSize: "10px", color: "#6e7681",
                    marginBottom: "10px", letterSpacing: "0.06em",
                    fontWeight: 500,
                  }}>
                    TEST {i + 1}: "{entry.message.slice(0, 40)}{entry.message.length > 40 ? '...' : ''}"
                  </div>
                  <DebugEntry entry={entry} />
                  {i < debugLog.length - 1 && (
                    <div style={{ height: "1px", background: "#21262d", margin: "18px 0" }} />
                  )}
                </div>
              ))}
              <div ref={debugEndRef} />
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
