import { useState, useEffect, useRef, useCallback } from "react";
import GmailIntegration from "./GmailIntegration";
import DeveloperPortal from "./DeveloperPortal";
import UnifiedInbox from "./UnifiedInbox";
import WhatsAppIntegration from "./WhatsAppIntegration";
import VoiceCommand from "./VoiceCommand";
import VoiceAnalytics from "./VoiceAnalytics";
import OmniLive from "./OmniLive";

const RESPONSES = {
  automation: `Outstanding. Here's how AUREM's automation architecture works:

Scout Agent runs continuously — scanning competitors, market signals, and customer behavior. It feeds intelligence into every downstream decision.

Architect Agent translates intelligence into executable workflows. Inventory triggers, pricing rules, fulfillment logic — all built automatically based on your data.

Envoy Agent handles all customer communication across WhatsApp, SMS, and email — 24 hours a day, zero delays.

Closer Agent manages sales qualification and conversion sequences, escalating high-value opportunities at the right moment.

The Central Orchestrator coordinates all four — deduplicating actions, managing circuit breakers, and delivering weekly performance digests.

Which part of your operation would you like to automate first?`,

  intel: `Let me build you a performance intelligence framework.

AUREM tracks four core business dimensions:

Revenue Intelligence — real-time sales velocity, average order value, conversion funnel analysis, and revenue per customer cohort.

Customer Intelligence — lifetime value scoring, churn prediction, segment behavior patterns, and loyalty trajectory mapping.

Operational Intelligence — fulfillment efficiency, inventory turnover, supplier performance, and cost-per-acquisition tracking.

Growth Intelligence — market opportunity scoring, competitive positioning gaps, and channel attribution modeling.

The system surfaces insights automatically — no manual reporting. You receive a prioritized action list every morning.

What is your primary growth bottleneck right now?`,

  customer: `AUREM's customer engagement system operates in three intelligent layers:

Capture Layer — smart behavioral triggers that qualify customers before they even reach out. No cold leads.

Nurture Layer — automated WhatsApp sequences and personalized email flows that adapt tone and timing to each individual customer's behavior.

Convert and Retain Layer — purchase triggers, win-back campaigns, VIP escalation flows, and loyalty automation that transform one-time buyers into lifetime customers.

Everything runs through the Central Orchestrator — preventing message overload and ensuring every communication feels personal at scale.

What does your current customer journey look like from first contact to repeat purchase?`,

  agent: `AUREM's Agent Swarm is a production-grade multi-agent AI deployment:

Scout — Runs continuously scanning news, competitor pricing, and social signals. Feeds live intelligence to every other agent.

Architect — Designs automation workflows and business logic rules specific to your operation. Updates automatically as conditions change.

Envoy — Manages all outbound messaging with brand-consistent AI responses across WhatsApp, email, and SMS simultaneously.

Closer — Qualifies inbound leads and manages follow-up sequences, escalating to your team when conversion probability is highest.

Orchestrator — Coordinates all agents, manages rate limits, and sends performance summaries directly to your phone.

All agents run on OpenRouter with multi-LLM routing — automatically selecting Claude, GPT-4, or Gemini based on task complexity.

Which agent would create the most immediate impact for your business?`,

  default: `That's exactly the kind of question ORA is built for.

The most successful brands we work with share one fundamental principle — they build intelligent systems before they need them. Every process that depends on a human being present is a vulnerability waiting to break.

ORA identifies those vulnerabilities and replaces them with AI systems that learn your business logic, adapt to your customer patterns, and improve continuously without intervention.

Our deployment begins with a 48-hour operational audit — mapping every manual process, identifying the top three automation opportunities, and building working systems within the first week.

What is the single biggest operational challenge your business faces right now?`
};

function getAIResponse(msg) {
  const m = msg.toLowerCase();
  if (m.includes("automat") || m.includes("workflow") || m.includes("system") || m.includes("operat")) return RESPONSES.automation;
  if (m.includes("analyt") || m.includes("growth") || m.includes("revenue") || m.includes("perform") || m.includes("data") || m.includes("metric")) return RESPONSES.intel;
  if (m.includes("customer") || m.includes("whatsapp") || m.includes("crm") || m.includes("engag") || m.includes("retention")) return RESPONSES.customer;
  if (m.includes("agent") || m.includes("swarm") || m.includes("scout") || m.includes("deploy") || m.includes("ai")) return RESPONSES.agent;
  return RESPONSES.default;
}

const GOLD = "#c9a84c", GOLD2 = "#e2c97e", GDIM = "#8a6f2e";
const OB = "#0a0a0f", OB2 = "#0f0f18", OB3 = "#141420";
const WH2 = "#e8e4d8", MU = "#5a5a72", SV = "#a8b0c0";
const API_BASE = process.env.REACT_APP_BACKEND_URL || "";

// ═══════════════════════════════════════════════════════════════════════════════
// AUTOMATION ENGINE VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function AutomationEngineView() {
  const [workflows, setWorkflows] = useState([
    { id: 1, name: "Welcome Series", trigger: "New signup", status: "active", executions: 1247, success: 98.2 },
    { id: 2, name: "Abandoned Cart Recovery", trigger: "Cart abandoned 1hr", status: "active", executions: 892, success: 34.7 },
    { id: 3, name: "VIP Escalation", trigger: "Order > $500", status: "active", executions: 156, success: 100 },
    { id: 4, name: "Re-engagement Campaign", trigger: "Inactive 30 days", status: "paused", executions: 2341, success: 12.3 },
    { id: 5, name: "Review Request", trigger: "Order delivered", status: "active", executions: 3421, success: 22.1 },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Automation Engine</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Build and manage automated workflows</p>
        </div>
        <button style={{ padding: "10px 20px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 12 }}>+ New Workflow</button>
      </div>
      
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Active Workflows", value: workflows.filter(w => w.status === "active").length, color: "#4ade80" },
          { label: "Total Executions", value: workflows.reduce((a, w) => a + w.executions, 0).toLocaleString(), color: GOLD },
          { label: "Avg Success Rate", value: (workflows.reduce((a, w) => a + w.success, 0) / workflows.length).toFixed(1) + "%", color: "#60a5fa" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color, fontFamily: "monospace", marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 80px", padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 10, color: MU, letterSpacing: "0.08em" }}>
          <div>WORKFLOW</div><div>TRIGGER</div><div>STATUS</div><div>EXECUTIONS</div><div>SUCCESS</div><div></div>
        </div>
        {workflows.map(w => (
          <div key={w.id} style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 80px", padding: "14px 16px", borderBottom: `1px solid rgba(201,168,76,.05)`, alignItems: "center" }}>
            <div style={{ color: WH2, fontSize: 13 }}>{w.name}</div>
            <div style={{ color: SV, fontSize: 12 }}>{w.trigger}</div>
            <div><span style={{ padding: "3px 10px", borderRadius: 12, fontSize: 10, background: w.status === "active" ? "rgba(74,222,128,.15)" : "rgba(201,168,76,.1)", color: w.status === "active" ? "#4ade80" : GDIM }}>{w.status.toUpperCase()}</span></div>
            <div style={{ color: SV, fontSize: 13, fontFamily: "monospace" }}>{w.executions.toLocaleString()}</div>
            <div style={{ color: w.success > 50 ? "#4ade80" : w.success > 20 ? GOLD : "#f87171", fontSize: 13, fontFamily: "monospace" }}>{w.success}%</div>
            <div><button style={{ padding: "5px 12px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 10, cursor: "pointer" }}>Edit</button></div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS HUB VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function AnalyticsHubView() {
  const [timeRange, setTimeRange] = useState("7d");
  
  const metrics = {
    revenue: { value: "$48,290", change: "+12.4%", positive: true },
    orders: { value: "847", change: "+8.2%", positive: true },
    customers: { value: "2,341", change: "+15.7%", positive: true },
    aov: { value: "$57.02", change: "-2.1%", positive: false },
  };

  const chartData = [65, 78, 82, 74, 91, 88, 95, 87, 102, 98, 89, 94];

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Analytics Hub</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Business intelligence & performance metrics</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {["24h", "7d", "30d", "90d"].map(t => (
            <button key={t} onClick={() => setTimeRange(t)} style={{ padding: "6px 14px", background: timeRange === t ? `rgba(201,168,76,.15)` : "transparent", border: `1px solid ${timeRange === t ? GOLD : "rgba(201,168,76,.2)"}`, borderRadius: 6, color: timeRange === t ? GOLD : MU, fontSize: 11, cursor: "pointer" }}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {Object.entries(metrics).map(([key, { value, change, positive }]) => (
          <div key={key} style={{ padding: 20, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.1em", marginBottom: 8 }}>{key.toUpperCase()}</div>
            <div style={{ fontSize: 28, color: GOLD2, fontFamily: "monospace", marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 12, color: positive ? "#4ade80" : "#f87171" }}>{change} vs last period</div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, padding: 20 }}>
        <div style={{ fontSize: 12, color: MU, letterSpacing: "0.08em", marginBottom: 16 }}>REVENUE TREND</div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 150 }}>
          {chartData.map((v, i) => (
            <div key={i} style={{ flex: 1, background: `linear-gradient(180deg, ${GOLD} 0%, ${GDIM} 100%)`, borderRadius: "4px 4px 0 0", height: `${v}%`, opacity: 0.7 + (i / chartData.length) * 0.3, transition: "height 0.3s" }} />
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 9, color: MU }}>
          {["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].map(m => <span key={m}>{m}</span>)}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// AGENT SWARM VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function AgentSwarmView() {
  const [agents] = useState([
    { name: "Scout Agent", status: "SCANNING", color: "#4ade80", tasks: 147, lastRun: "2 min ago", description: "Market intelligence & competitor monitoring" },
    { name: "Architect Agent", status: "BUILDING", color: "#f59e0b", tasks: 23, lastRun: "8 min ago", description: "Workflow design & automation rules" },
    { name: "Envoy Agent", status: "LIVE", color: "#4ade80", tasks: 892, lastRun: "Just now", description: "Customer communication across all channels" },
    { name: "Closer Agent", status: "STANDBY", color: GDIM, tasks: 56, lastRun: "1 hr ago", description: "Sales qualification & conversion sequences" },
    { name: "Orchestrator", status: "MANAGING", color: "#4ade80", tasks: 1247, lastRun: "Just now", description: "Central coordination & rate limiting" },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Agent Swarm</h2>
        <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Multi-agent AI deployment status & control</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 16 }}>
        {agents.map(agent => (
          <div key={agent.name} style={{ padding: 20, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: agent.color, boxShadow: agent.color !== GDIM ? `0 0 12px ${agent.color}` : "none" }} />
                  <span style={{ fontSize: 15, color: WH2 }}>{agent.name}</span>
                </div>
                <div style={{ fontSize: 11, color: MU, marginTop: 4, marginLeft: 20 }}>{agent.description}</div>
              </div>
              <span style={{ padding: "4px 12px", borderRadius: 12, fontSize: 10, background: agent.status === "LIVE" || agent.status === "SCANNING" || agent.status === "MANAGING" ? "rgba(74,222,128,.15)" : agent.status === "BUILDING" ? "rgba(245,158,11,.15)" : "rgba(201,168,76,.1)", color: agent.color, letterSpacing: "0.05em" }}>{agent.status}</span>
            </div>
            <div style={{ display: "flex", gap: 24, marginTop: 16 }}>
              <div>
                <div style={{ fontSize: 20, color: GOLD2, fontFamily: "monospace" }}>{agent.tasks}</div>
                <div style={{ fontSize: 9, color: MU }}>Tasks completed</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: SV }}>{agent.lastRun}</div>
                <div style={{ fontSize: 9, color: MU }}>Last activity</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button style={{ flex: 1, padding: "8px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 10, cursor: "pointer" }}>View Logs</button>
              <button style={{ flex: 1, padding: "8px", background: agent.status === "STANDBY" ? `rgba(74,222,128,.15)` : `rgba(239,68,68,.15)`, border: "none", borderRadius: 6, color: agent.status === "STANDBY" ? "#4ade80" : "#ef4444", fontSize: 10, cursor: "pointer" }}>{agent.status === "STANDBY" ? "Activate" : "Pause"}</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CRM CONNECT VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function CRMConnectView() {
  const [customers] = useState([
    { id: 1, name: "Sarah Chen", email: "sarah@example.com", ltv: 1247, orders: 8, segment: "VIP", lastOrder: "2 days ago" },
    { id: 2, name: "Marcus Williams", email: "marcus@example.com", ltv: 892, orders: 5, segment: "Active", lastOrder: "1 week ago" },
    { id: 3, name: "Emma Thompson", email: "emma@example.com", ltv: 2341, orders: 12, segment: "VIP", lastOrder: "Yesterday" },
    { id: 4, name: "James Rodriguez", email: "james@example.com", ltv: 156, orders: 1, segment: "New", lastOrder: "Just now" },
    { id: 5, name: "Olivia Park", email: "olivia@example.com", ltv: 567, orders: 3, segment: "Active", lastOrder: "3 days ago" },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>CRM Connect</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Customer relationship management powered by AI</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button style={{ padding: "10px 20px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 8, color: GOLD, fontSize: 12, cursor: "pointer" }}>Import</button>
          <button style={{ padding: "10px 20px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 12 }}>+ Add Customer</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Total Customers", value: "2,847", icon: "👥" },
          { label: "VIP Customers", value: "156", icon: "⭐" },
          { label: "Avg LTV", value: "$423", icon: "💰" },
          { label: "Churn Risk", value: "3.2%", icon: "⚠️" },
        ].map(({ label, value, icon }) => (
          <div key={label} style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8, display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ fontSize: 24 }}>{icon}</div>
            <div>
              <div style={{ fontSize: 18, color: GOLD2, fontFamily: "monospace" }}>{value}</div>
              <div style={{ fontSize: 10, color: MU }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 2fr 1fr 1fr 1fr 1fr", padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 10, color: MU, letterSpacing: "0.08em" }}>
          <div>CUSTOMER</div><div>EMAIL</div><div>LTV</div><div>ORDERS</div><div>SEGMENT</div><div>LAST ORDER</div>
        </div>
        {customers.map(c => (
          <div key={c.id} style={{ display: "grid", gridTemplateColumns: "2fr 2fr 1fr 1fr 1fr 1fr", padding: "14px 16px", borderBottom: `1px solid rgba(201,168,76,.05)`, alignItems: "center", cursor: "pointer" }} onMouseEnter={e => e.currentTarget.style.background = "rgba(201,168,76,.03)"} onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            <div style={{ color: WH2, fontSize: 13 }}>{c.name}</div>
            <div style={{ color: SV, fontSize: 12 }}>{c.email}</div>
            <div style={{ color: GOLD2, fontSize: 13, fontFamily: "monospace" }}>${c.ltv}</div>
            <div style={{ color: SV, fontSize: 13 }}>{c.orders}</div>
            <div><span style={{ padding: "3px 10px", borderRadius: 12, fontSize: 10, background: c.segment === "VIP" ? "rgba(201,168,76,.15)" : c.segment === "Active" ? "rgba(74,222,128,.15)" : "rgba(96,165,250,.15)", color: c.segment === "VIP" ? GOLD : c.segment === "Active" ? "#4ade80" : "#60a5fa" }}>{c.segment}</span></div>
            <div style={{ color: MU, fontSize: 12 }}>{c.lastOrder}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// WHATSAPP FLOWS VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function WhatsAppFlowsView() {
  const [flows] = useState([
    { id: 1, name: "Welcome Message", trigger: "New customer", sent: 2847, delivered: 98.2, read: 87.4, replied: 34.2 },
    { id: 2, name: "Order Confirmation", trigger: "Order placed", sent: 8923, delivered: 99.1, read: 91.2, replied: 12.1 },
    { id: 3, name: "Shipping Update", trigger: "Order shipped", sent: 7841, delivered: 98.8, read: 89.7, replied: 8.3 },
    { id: 4, name: "Abandoned Cart", trigger: "Cart abandoned 1hr", sent: 1247, delivered: 97.4, read: 72.1, replied: 23.4 },
    { id: 5, name: "Review Request", trigger: "Order delivered", sent: 5621, delivered: 98.9, read: 68.2, replied: 18.7 },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>WhatsApp Flows</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Automated messaging campaigns via WhatsApp Business</p>
        </div>
        <button style={{ padding: "10px 20px", background: `linear-gradient(135deg, #25D366, #128C7E)`, border: "none", borderRadius: 8, color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 12 }}>+ New Flow</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Messages Sent", value: "26.4K", color: "#25D366" },
          { label: "Delivery Rate", value: "98.4%", color: GOLD },
          { label: "Read Rate", value: "81.7%", color: "#60a5fa" },
          { label: "Reply Rate", value: "19.3%", color: "#a855f7" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color, fontFamily: "monospace", marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>{label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 1fr 80px", padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 10, color: MU, letterSpacing: "0.08em" }}>
          <div>FLOW NAME</div><div>TRIGGER</div><div>SENT</div><div>DELIVERED</div><div>READ</div><div>REPLIED</div><div></div>
        </div>
        {flows.map(f => (
          <div key={f.id} style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr 1fr 1fr 1fr 80px", padding: "14px 16px", borderBottom: `1px solid rgba(201,168,76,.05)`, alignItems: "center" }}>
            <div style={{ color: WH2, fontSize: 13 }}>{f.name}</div>
            <div style={{ color: SV, fontSize: 12 }}>{f.trigger}</div>
            <div style={{ color: SV, fontSize: 13, fontFamily: "monospace" }}>{f.sent.toLocaleString()}</div>
            <div style={{ color: "#4ade80", fontSize: 13, fontFamily: "monospace" }}>{f.delivered}%</div>
            <div style={{ color: "#60a5fa", fontSize: 13, fontFamily: "monospace" }}>{f.read}%</div>
            <div style={{ color: "#a855f7", fontSize: 13, fontFamily: "monospace" }}>{f.replied}%</div>
            <div><button style={{ padding: "5px 12px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 10, cursor: "pointer" }}>Edit</button></div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// API GATEWAY VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function APIGatewayView() {
  const [apiKeys] = useState([
    { id: 1, name: "Production Key", key: "ak_live_****8f2a", created: "Jan 15, 2025", lastUsed: "2 min ago", requests: 124789 },
    { id: 2, name: "Development Key", key: "ak_test_****3b1c", created: "Dec 3, 2024", lastUsed: "1 hr ago", requests: 8921 },
    { id: 3, name: "Webhook Key", key: "ak_whk_****9d4e", created: "Feb 1, 2025", lastUsed: "Just now", requests: 45621 },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>API Gateway</h2>
          <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Manage API keys and integrations</p>
        </div>
        <button style={{ padding: "10px 20px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 12 }}>+ Generate Key</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "Total Requests", value: "179.3K", trend: "+12% today" },
          { label: "Avg Latency", value: "89ms", trend: "↓ 15ms" },
          { label: "Error Rate", value: "0.02%", trend: "Stable" },
        ].map(({ label, value, trend }) => (
          <div key={label} style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 24, color: GOLD2, fontFamily: "monospace", marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em" }}>{label}</div>
            <div style={{ fontSize: 10, color: "#4ade80", marginTop: 4 }}>{trend}</div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden", marginBottom: 24 }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 12, color: MU, letterSpacing: "0.08em" }}>API KEYS</div>
        {apiKeys.map(k => (
          <div key={k.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", borderBottom: `1px solid rgba(201,168,76,.05)` }}>
            <div>
              <div style={{ color: WH2, fontSize: 14, marginBottom: 4 }}>{k.name}</div>
              <div style={{ fontFamily: "monospace", fontSize: 12, color: GDIM }}>{k.key}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 12, color: SV }}>{k.requests.toLocaleString()} requests</div>
              <div style={{ fontSize: 10, color: MU }}>Last used: {k.lastUsed}</div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button style={{ padding: "6px 12px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 10, cursor: "pointer" }}>Copy</button>
              <button style={{ padding: "6px 12px", background: "rgba(239,68,68,.1)", border: "none", borderRadius: 6, color: "#ef4444", fontSize: 10, cursor: "pointer" }}>Revoke</button>
            </div>
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, padding: 20 }}>
        <div style={{ fontSize: 12, color: MU, letterSpacing: "0.08em", marginBottom: 16 }}>QUICK START</div>
        <pre style={{ background: OB, padding: 16, borderRadius: 8, overflow: "auto", fontSize: 12, color: SV }}>{`curl -X POST ${API_BASE}/api/aurem/query \\
  -H "Authorization: Bearer ak_live_****8f2a" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "Get customer insights"}'`}</pre>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SETTINGS VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function SettingsView() {
  const [settings, setSettings] = useState({
    notifications: true,
    emailDigest: true,
    voiceEnabled: true,
    darkMode: true,
    autoRespond: false,
  });

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Settings</h2>
        <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Configure your AUREM platform preferences</p>
      </div>

      <div style={{ maxWidth: 600 }}>
        {[
          { key: "notifications", label: "Push Notifications", desc: "Receive real-time alerts for important events" },
          { key: "emailDigest", label: "Daily Email Digest", desc: "Get a summary of your AI activity every morning" },
          { key: "voiceEnabled", label: "Voice Responses", desc: "Enable text-to-speech for AI responses" },
          { key: "darkMode", label: "Dark Mode", desc: "Use dark theme across the platform" },
          { key: "autoRespond", label: "Auto-Respond Mode", desc: "Let AI handle customer queries automatically" },
        ].map(({ key, label, desc }) => (
          <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "20px 0", borderBottom: `1px solid rgba(201,168,76,.1)` }}>
            <div>
              <div style={{ color: WH2, fontSize: 14, marginBottom: 4 }}>{label}</div>
              <div style={{ color: MU, fontSize: 12 }}>{desc}</div>
            </div>
            <button
              onClick={() => setSettings(s => ({ ...s, [key]: !s[key] }))}
              style={{ width: 48, height: 26, borderRadius: 13, border: "none", background: settings[key] ? GOLD : "rgba(201,168,76,.2)", cursor: "pointer", position: "relative", transition: "background 0.2s" }}
            >
              <div style={{ width: 20, height: 20, borderRadius: "50%", background: WH2, position: "absolute", top: 3, left: settings[key] ? 25 : 3, transition: "left 0.2s" }} />
            </button>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 32 }}>
        <h3 style={{ fontSize: 14, color: GOLD2, margin: "0 0 16px", letterSpacing: "0.08em" }}>DANGER ZONE</h3>
        <div style={{ display: "flex", gap: 12 }}>
          <button style={{ padding: "10px 20px", background: "rgba(239,68,68,.1)", border: `1px solid rgba(239,68,68,.3)`, borderRadius: 8, color: "#ef4444", fontSize: 12, cursor: "pointer" }}>Reset All Settings</button>
          <button style={{ padding: "10px 20px", background: "rgba(239,68,68,.1)", border: `1px solid rgba(239,68,68,.3)`, borderRadius: 8, color: "#ef4444", fontSize: 12, cursor: "pointer" }}>Delete Account</button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// USAGE & BILLING VIEW
// ═══════════════════════════════════════════════════════════════════════════════
function UsageBillingView() {
  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 20, color: GOLD2, margin: 0, letterSpacing: "0.1em" }}>Usage & Billing</h2>
        <p style={{ fontSize: 12, color: MU, margin: "4px 0 0" }}>Monitor your usage and manage subscription</p>
      </div>

      <div style={{ background: `linear-gradient(135deg, rgba(201,168,76,.15) 0%, rgba(201,168,76,.05) 100%)`, border: `1px solid rgba(201,168,76,.2)`, borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.1em", marginBottom: 4 }}>CURRENT PLAN</div>
            <div style={{ fontSize: 24, color: GOLD2, marginBottom: 4 }}>Enterprise</div>
            <div style={{ fontSize: 12, color: SV }}>Unlimited AI queries • Priority support • All integrations</div>
          </div>
          <button style={{ padding: "12px 24px", background: `linear-gradient(135deg, ${GOLD}, ${GDIM})`, border: "none", borderRadius: 8, color: OB, fontWeight: 600, cursor: "pointer", fontSize: 12 }}>Manage Plan</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {[
          { label: "AI Queries", used: 12847, limit: "Unlimited", percent: null },
          { label: "WhatsApp Messages", used: 8923, limit: 10000, percent: 89 },
          { label: "Email Campaigns", used: 47, limit: 100, percent: 47 },
          { label: "API Calls", used: 179321, limit: 500000, percent: 36 },
        ].map(({ label, used, limit, percent }) => (
          <div key={label} style={{ padding: 16, background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 8 }}>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em", marginBottom: 8 }}>{label}</div>
            <div style={{ fontSize: 20, color: GOLD2, fontFamily: "monospace" }}>{used.toLocaleString()}</div>
            <div style={{ fontSize: 11, color: SV, marginTop: 4 }}>of {typeof limit === "number" ? limit.toLocaleString() : limit}</div>
            {percent !== null && (
              <div style={{ height: 4, background: "rgba(201,168,76,.1)", borderRadius: 2, marginTop: 8 }}>
                <div style={{ height: "100%", width: `${percent}%`, background: percent > 80 ? "#f87171" : GOLD, borderRadius: 2 }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div style={{ background: OB3, border: `1px solid rgba(201,168,76,.1)`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: `1px solid rgba(201,168,76,.1)`, fontSize: 12, color: MU, letterSpacing: "0.08em" }}>BILLING HISTORY</div>
        {[
          { date: "Feb 1, 2025", desc: "Enterprise Plan - Monthly", amount: "$499.00", status: "Paid" },
          { date: "Jan 1, 2025", desc: "Enterprise Plan - Monthly", amount: "$499.00", status: "Paid" },
          { date: "Dec 1, 2024", desc: "Enterprise Plan - Monthly", amount: "$499.00", status: "Paid" },
        ].map((invoice, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", borderBottom: `1px solid rgba(201,168,76,.05)` }}>
            <div>
              <div style={{ color: WH2, fontSize: 13 }}>{invoice.desc}</div>
              <div style={{ color: MU, fontSize: 11, marginTop: 2 }}>{invoice.date}</div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <span style={{ color: GOLD2, fontFamily: "monospace", fontSize: 14 }}>{invoice.amount}</span>
              <span style={{ padding: "3px 10px", borderRadius: 12, fontSize: 10, background: "rgba(74,222,128,.15)", color: "#4ade80" }}>{invoice.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function AuremAI() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [recording, setRecording] = useState(false);
  const [activeNav, setActiveNav] = useState("AI Conversation");
  const [sessionId] = useState("ORA-" + Math.random().toString(36).substr(2, 6).toUpperCase());
  const [displayedText, setDisplayedText] = useState({});
  const [metrics, setMetrics] = useState({ queries: 2847, response: "1.2s", brands: 47 });
  const [liveActivities, setLiveActivities] = useState([]);
  const [agentStatuses, setAgentStatuses] = useState({});
  const messagesEnd = useRef(null);
  const synth = useRef(typeof window !== "undefined" ? window.speechSynthesis : null);
  const recRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, typing, displayedText]);

  // WebSocket connection for real-time updates
  useEffect(() => {
    const wsUrl = API_BASE.replace("https://", "wss://").replace("http://", "ws://") + `/api/aurem-redis/ws/${sessionId}`;
    
    const connect = () => {
      try {
        wsRef.current = new WebSocket(wsUrl);
        
        wsRef.current.onopen = () => {
          console.log("[AUREM WS] Connected");
          // Send ping every 30s to keep alive
          const pingInterval = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: "ping" }));
            }
          }, 30000);
          wsRef.current.pingInterval = pingInterval;
        };
        
        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === "activity") {
              setLiveActivities(prev => [{
                id: Date.now(),
                type: data.activity_type,
                description: data.description,
                timestamp: data.timestamp
              }, ...prev].slice(0, 20));
            }
            
            if (data.type === "agent_status") {
              setAgentStatuses(prev => ({
                ...prev,
                [data.agent]: { status: data.status, taskCount: data.task_count }
              }));
            }
            
            if (data.type === "metrics") {
              setMetrics(prev => ({ ...prev, ...data.metrics }));
            }
          } catch (e) {
            console.log("[AUREM WS] Parse error:", e);
          }
        };
        
        wsRef.current.onclose = () => {
          console.log("[AUREM WS] Disconnected, reconnecting...");
          if (wsRef.current?.pingInterval) clearInterval(wsRef.current.pingInterval);
          setTimeout(connect, 3000);
        };
        
        wsRef.current.onerror = (err) => {
          console.log("[AUREM WS] Error:", err);
        };
      } catch (e) {
        console.log("[AUREM WS] Connection failed:", e);
      }
    };
    
    connect();
    
    return () => {
      if (wsRef.current?.pingInterval) clearInterval(wsRef.current.pingInterval);
      wsRef.current?.close();
    };
  }, [sessionId]);

  // Sync voice state across devices via Redis
  useEffect(() => {
    const syncState = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/aurem-redis/state/${sessionId}/voice_enabled`);
        const data = await res.json();
        if (data.value !== null && data.value !== undefined) {
          setVoiceOn(data.value);
        }
      } catch (e) {
        // Ignore - Redis may not be available
      }
    };
    syncState();
  }, [sessionId]);

  const updateVoiceState = async (enabled) => {
    try {
      await fetch(`${API_BASE}/api/aurem-redis/state/${sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: "voice_enabled", value: enabled })
      });
    } catch (e) {
      // Ignore
    }
  };

  useEffect(() => {
    const t = setInterval(() => {
      setMetrics(m => ({ queries: m.queries + Math.floor(Math.random() * 3 + 1), response: (0.8 + Math.random() * 0.8).toFixed(1) + "s", brands: Math.random() > 0.93 ? m.brands + 1 : m.brands }));
    }, 7000);
    return () => clearInterval(t);
  }, []);

  const typewrite = useCallback((id, text) => {
    let i = 0;
    setDisplayedText(p => ({ ...p, [id]: "" }));
    const iv = setInterval(() => {
      i++;
      setDisplayedText(p => ({ ...p, [id]: text.slice(0, i) }));
      if (i >= text.length) {
        clearInterval(iv);
        if (voiceOn && synth.current) {
          const u = new SpeechSynthesisUtterance(text.replace(/\n/g, " "));
          u.rate = 0.88; u.pitch = 0.95;
          const vs = synth.current.getVoices();
          const v = vs.find(x => x.name.includes("Daniel") || x.name.includes("Karen") || x.lang === "en-GB") || vs[0];
          if (v) u.voice = v;
          u.onstart = () => setSpeaking(true);
          u.onend = u.onerror = () => setSpeaking(false);
          synth.current.speak(u);
        }
      }
    }, 14);
  }, [voiceOn]);

  const sendMsg = useCallback(async (txt) => {
    const text = txt || input.trim();
    if (!text) return;
    setInput("");
    const now = new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    setMessages(p => [...p, { id: Date.now(), role: "user", text, time: now }]);
    setTyping(true);
    await new Promise(r => setTimeout(r, 800 + Math.random() * 600));
    const resp = getAIResponse(text);
    const aid = Date.now() + 1;
    setTyping(false);
    setMessages(p => [...p, { id: aid, role: "aurem", text: resp, time: new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) }]);
    typewrite(aid, resp);
  }, [input, typewrite]);

  const toggleVoice = () => { 
    if (voiceOn && synth.current) { synth.current.cancel(); setSpeaking(false); } 
    setVoiceOn(p => { 
      const newVal = !p; 
      updateVoiceState(newVal); 
      return newVal; 
    }); 
  };
  const stopSpeak = () => { synth.current?.cancel(); setSpeaking(false); };

  const toggleMic = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { sendMsg("Voice input requires Chrome browser for the full ORA voice experience."); return; }
    if (recording) { recRef.current?.stop(); return; }
    recRef.current = new SR();
    recRef.current.continuous = false; recRef.current.interimResults = true; recRef.current.lang = "en-US";
    recRef.current.onstart = () => setRecording(true);
    recRef.current.onresult = e => setInput(Array.from(e.results).map(r => r[0].transcript).join(""));
    recRef.current.onend = () => setRecording(false);
    recRef.current.onerror = () => setRecording(false);
    recRef.current.start();
  };

  const navSections = [
    { title: "COMMAND CENTER", items: ["Unified Inbox", "Voice Command", "Voice Analytics", "Omni-Live"] },
    { title: "WORKSPACE", items: ["AI Conversation", "Automation Engine", "Analytics Hub", "Agent Swarm"] },
    { title: "INTEGRATIONS", items: ["Gmail Channel", "CRM Connect", "WhatsApp Flows", "API Gateway"] },
    { title: "DEVELOPER", items: ["Developer Portal"] },
    { title: "ACCOUNT", items: ["Settings", "Usage & Billing"] }
  ];

  const agents = [
    { name: "Scout Agent", status: agentStatuses["Scout Agent"]?.status || "SCANNING", color: "#4ade80" },
    { name: "Architect Agent", status: agentStatuses["Architect Agent"]?.status || "BUILDING", color: "#f59e0b" },
    { name: "Envoy Agent", status: agentStatuses["Envoy Agent"]?.status || "LIVE", color: "#4ade80" },
    { name: "Closer Agent", status: agentStatuses["Closer Agent"]?.status || "STANDBY", color: GDIM },
    { name: "Orchestrator", status: agentStatuses["Orchestrator"]?.status || "MANAGING", color: "#4ade80" }
  ];

  const quickActions = [
    { icon: "⚡", title: "Automation Strategy", desc: "Build systems that run 24/7", msg: "How can ORA automate my entire business operation?" },
    { icon: "◈", title: "Business Intelligence", desc: "Data-driven decisions", msg: "Analyze my business performance and show growth opportunities" },
    { icon: "◎", title: "Customer Engagement", desc: "AI-powered CRM flows", msg: "Design a customer engagement system with AI and WhatsApp" },
    { icon: "⬡", title: "Deploy Agent Swarm", desc: "Scout · Architect · Closer", msg: "What AI agent swarm can you deploy for my brand right now?" }
  ];

  // Render the appropriate view based on activeNav
  const renderMainContent = () => {
    switch (activeNav) {
      case "Unified Inbox":
        return <UnifiedInbox businessId={sessionId} />;
      case "Voice Command":
        return <VoiceCommand businessId={sessionId} />;
      case "Voice Analytics":
        return <VoiceAnalytics businessId={sessionId} />;
      case "Omni-Live":
        return <OmniLive businessId={sessionId} />;
      case "Automation Engine":
        return <AutomationEngineView />;
      case "Analytics Hub":
        return <AnalyticsHubView />;
      case "Agent Swarm":
        return <AgentSwarmView />;
      case "Gmail Channel":
        return <GmailIntegration businessId={sessionId} />;
      case "CRM Connect":
        return <CRMConnectView />;
      case "WhatsApp Flows":
        return <WhatsAppIntegration businessId={sessionId} />;
      case "API Gateway":
        return <APIGatewayView />;
      case "Developer Portal":
        return <DeveloperPortal businessId={sessionId} />;
      case "Settings":
        return <SettingsView />;
      case "Usage & Billing":
        return <UsageBillingView />;
      default:
        return null; // AI Conversation view
    }
  };

  const showChatView = activeNav === "AI Conversation";

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", background: OB, color: WH2, height: "100vh", display: "grid", gridTemplateColumns: "220px 1fr 240px", overflow: "hidden", fontSize: 13, position: "fixed", top: 0, left: 0, right: 0, bottom: 0, zIndex: 99999 }}>
      <style>{`
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes dots{0%,100%{transform:translateY(0);opacity:.4}50%{transform:translateY(-5px);opacity:1}}
        @keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        @keyframes wave{0%,100%{transform:scaleY(.4);opacity:.5}50%{transform:scaleY(1);opacity:1}}
        @keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
        ::-webkit-scrollbar{width:3px}
        ::-webkit-scrollbar-thumb{background:rgba(201,168,76,.2);border-radius:2px}
        textarea{font-family:inherit;resize:none}
      `}</style>

      {/* SIDEBAR */}
      <div style={{ background: OB2, borderRight: `1px solid rgba(201,168,76,.1)`, padding: "20px 16px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ marginBottom: 24 }}>
          <div style={{ width: 36, height: 36, border: `1px solid ${GDIM}`, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 8, animation: "spin 20s linear infinite" }}>
            <svg viewBox="0 0 24 24" fill="none" stroke={GOLD} strokeWidth="1.2" width="15" height="15"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2"/></svg>
          </div>
          <div style={{ fontSize: 18, letterSpacing: "0.3em", color: GOLD2, fontWeight: 300 }}>ORA</div>
          <div style={{ fontSize: 8, letterSpacing: "0.2em", color: MU, marginTop: 2 }}>BY AUREM AI</div>
        </div>
        {navSections.map(({ title, items }) => (
          <div key={title} style={{ marginBottom: 4 }}>
            <div style={{ fontSize: 8, letterSpacing: "0.25em", color: GDIM, padding: "8px 8px 4px" }}>{title}</div>
            {items.map(item => (
              <div key={item} onClick={() => setActiveNav(item)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 6, fontSize: 11, color: activeNav === item ? GOLD : MU, background: activeNav === item ? "rgba(201,168,76,.07)" : "transparent", border: `1px solid ${activeNav === item ? "rgba(201,168,76,.15)" : "transparent"}`, cursor: "pointer", marginBottom: 1, transition: "all .2s" }}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: activeNav === item ? GOLD : MU, boxShadow: activeNav === item ? `0 0 6px ${GOLD}` : "none", flexShrink: 0 }} />
                {item}
              </div>
            ))}
            <div style={{ height: 1, background: "rgba(201,168,76,.07)", margin: "8px 0" }} />
          </div>
        ))}
        <div style={{ marginTop: "auto", display: "flex", alignItems: "center", gap: 7, padding: "8px 10px", background: "rgba(201,168,76,.04)", border: "1px solid rgba(201,168,76,.1)", borderRadius: 6 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", boxShadow: "0 0 8px #4ade80", animation: "pulse 2s infinite", flexShrink: 0 }} />
          <span style={{ fontSize: 9, color: SV, letterSpacing: "0.04em" }}>ALL SYSTEMS OPERATIONAL</span>
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      {showChatView ? (
        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", background: OB }}>
          <div style={{ padding: "14px 22px", borderBottom: "1px solid rgba(201,168,76,.08)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(10,10,15,.95)", flexShrink: 0 }}>
            <div>
              <div style={{ fontSize: 14, letterSpacing: "0.12em", color: WH2, fontWeight: 400 }}>ORA Intelligence</div>
              <div style={{ fontSize: 9, letterSpacing: "0.08em", color: MU, marginTop: 2 }}>Powered by AUREM — Multi-Agent Business AI</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <div style={{ fontFamily: "monospace", fontSize: 9, color: MU, padding: "3px 8px", border: "1px solid rgba(201,168,76,.1)", borderRadius: 4 }}>{sessionId}</div>
              {/* Prominent Voice Toggle Button */}
              <button 
                onClick={toggleVoice} 
                title={voiceOn ? "Click to disable voice responses" : "Click to enable voice responses"}
                style={{ 
                  display: "flex", 
                  alignItems: "center", 
                  gap: 6, 
                  padding: "7px 14px", 
                  border: `2px solid ${voiceOn ? "#D4AF37" : "rgba(201,168,76,.25)"}`, 
                  borderRadius: 20, 
                  background: voiceOn ? "linear-gradient(135deg, #D4AF37 0%, #8B7355 100%)" : "rgba(201,168,76,.08)", 
                  color: voiceOn ? "#050505" : GOLD2, 
                  fontSize: 11, 
                  fontWeight: 600,
                  cursor: "pointer", 
                  letterSpacing: "0.08em",
                  transition: "all 0.3s",
                  boxShadow: voiceOn ? "0 0 15px rgba(212,175,55,.3)" : "none"
                }}
              >
                <span style={{ fontSize: 14 }}>{voiceOn ? "🔊" : "🔇"}</span>
                {voiceOn ? "VOICE ON" : "VOICE OFF"}
              </button>
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "20px 22px", display: "flex", flexDirection: "column", gap: 16 }}>
            {messages.length === 0 && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, textAlign: "center", animation: "fadeIn .8s ease" }}>
                <div style={{ width: 56, height: 56, border: `1px solid rgba(201,168,76,.35)`, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 18, boxShadow: "0 0 30px rgba(201,168,76,.15)" }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke={GOLD} strokeWidth="1" width="22" height="22"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.6 5.6l2 2M16.4 16.4l2 2M5.6 18.4l2-2M16.4 7.6l2-2"/></svg>
                </div>
                <div style={{ fontSize: 36, letterSpacing: "0.25em", color: GOLD2, fontWeight: 300, lineHeight: 1 }}>ORA</div>
                <div style={{ fontSize: 9, letterSpacing: "0.3em", color: MU, margin: "6px 0 12px" }}>BUSINESS INTELLIGENCE AI</div>
                <div style={{ fontSize: 14, color: SV, maxWidth: 360, lineHeight: 1.75, marginBottom: 28, fontStyle: "italic" }}>Hello. I'm ORA — AUREM's business intelligence engine. Ready to help your business grow smarter.</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, width: "100%", maxWidth: 420 }}>
                  {quickActions.map(({ icon, title, desc, msg }) => (
                    <div key={title} onClick={() => sendMsg(msg)} style={{ padding: "12px 14px", border: "1px solid rgba(201,168,76,.15)", borderRadius: 8, background: "rgba(201,168,76,.03)", cursor: "pointer", textAlign: "left", transition: "all .2s" }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(201,168,76,.4)"; e.currentTarget.style.background = "rgba(201,168,76,.08)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(201,168,76,.15)"; e.currentTarget.style.background = "rgba(201,168,76,.03)"; e.currentTarget.style.transform = "translateY(0)"; }}>
                      <div style={{ fontSize: 20, marginBottom: 5 }}>{icon}</div>
                      <div style={{ fontSize: 11, fontWeight: 500, color: GOLD2, letterSpacing: "0.04em" }}>{title}</div>
                      <div style={{ fontSize: 10, color: MU, marginTop: 3 }}>{desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map(msg => (
              <div key={msg.id} style={{ display: "flex", gap: 10, animation: "msgIn .35s ease", maxWidth: "86%", alignSelf: msg.role === "user" ? "flex-end" : "flex-start", flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", border: `1px solid rgba(201,168,76,.3)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 9, color: GOLD, background: msg.role === "aurem" ? "rgba(201,168,76,.06)" : "rgba(201,168,76,.12)", letterSpacing: "0.05em" }}>
                  {msg.role === "aurem" ? "OR" : "ME"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ padding: "12px 15px", border: `1px solid ${msg.role === "user" ? "rgba(201,168,76,.2)" : "rgba(255,255,255,.06)"}`, borderRadius: msg.role === "user" ? "12px 4px 12px 12px" : "4px 12px 12px 12px", background: msg.role === "user" ? "linear-gradient(135deg,rgba(201,168,76,.14),rgba(201,168,76,.06))" : OB3, fontSize: 13, lineHeight: 1.75, color: WH2, whiteSpace: "pre-line" }}>
                    {msg.role === "aurem" ? (displayedText[msg.id] ?? "") : msg.text}
                    {msg.role === "aurem" && (displayedText[msg.id]?.length ?? 0) < msg.text.length && <span style={{ display: "inline-block", width: 2, height: 14, background: GOLD, marginLeft: 2, animation: "pulse 1s infinite", verticalAlign: "text-bottom" }} />}
                  </div>
                  <div style={{ fontSize: 9, color: MU, marginTop: 4, textAlign: msg.role === "user" ? "right" : "left", letterSpacing: "0.04em" }}>{msg.time} · {msg.role === "aurem" ? "ORA" : "You"}</div>
                </div>
              </div>
            ))}

            {typing && (
              <div style={{ display: "flex", gap: 10, animation: "msgIn .35s ease" }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", border: `1px solid rgba(201,168,76,.3)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: GOLD, background: "rgba(201,168,76,.06)", flexShrink: 0 }}>OR</div>
                <div style={{ padding: "14px 18px", border: "1px solid rgba(255,255,255,.06)", borderRadius: "4px 12px 12px 12px", background: OB3, display: "flex", gap: 5, alignItems: "center" }}>
                  <span style={{ fontSize: 10, color: MU, marginRight: 8 }}>ORA is thinking</span>
                  {[0,1,2].map(i => <div key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: GDIM, animation: `dots 1.4s infinite`, animationDelay: `${i*0.2}s` }} />)}
                </div>
              </div>
            )}

            {speaking && (
              <div style={{ position: "fixed", bottom: 80, left: "50%", transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: 12, padding: "9px 18px", background: "rgba(10,10,15,.96)", border: `1px solid rgba(201,168,76,.35)`, borderRadius: 30, zIndex: 100, boxShadow: "0 8px 32px rgba(0,0,0,.6)" }}>
                <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
                  {[8,13,18,11,15,9,13].map((h, i) => <div key={i} style={{ width: 3, height: h, background: GOLD, borderRadius: 2, animation: `wave 1.2s ease infinite`, animationDelay: `${i*0.1}s` }} />)}
                </div>
                <span style={{ fontSize: 10, color: GOLD2, letterSpacing: "0.1em" }}>ORA IS SPEAKING</span>
                <button onClick={stopSpeak} style={{ background: "none", border: `1px solid rgba(201,168,76,.3)`, color: GOLD, fontSize: 9, padding: "3px 9px", borderRadius: 10, cursor: "pointer", letterSpacing: "0.05em" }}>STOP</button>
              </div>
            )}
            <div ref={messagesEnd} />
          </div>

          <div style={{ padding: "14px 22px", borderTop: "1px solid rgba(201,168,76,.08)", background: "rgba(10,10,15,.96)", flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 9, padding: "10px 14px", border: "1px solid rgba(201,168,76,.18)", borderRadius: 12, background: OB3 }}>
              <textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMsg(); } }} placeholder={recording ? "🎤 Listening..." : "Ask ORA anything about your business..."} rows={1} style={{ flex: 1, background: "none", border: "none", outline: "none", color: WH2, fontSize: 13, letterSpacing: "0.02em", maxHeight: 100, lineHeight: 1.6, overflow: "hidden" }} />
              <div style={{ display: "flex", gap: 7, alignItems: "center", flexShrink: 0 }}>
                {recording && <div style={{ display: "flex", gap: 2 }}>{[8,14,18,12,16].map((h,i) => <div key={i} style={{ width: 3, height: h, background: GOLD, borderRadius: 2, animation: `wave 1.2s ease infinite`, animationDelay: `${i*0.1}s` }} />)}</div>}
                <button onClick={toggleMic} style={{ width: 32, height: 32, borderRadius: "50%", border: `1px solid ${recording ? "rgba(239,68,68,.5)" : "rgba(201,168,76,.2)"}`, background: recording ? "rgba(239,68,68,.12)" : "transparent", cursor: "pointer", fontSize: 14, color: recording ? "#ef4444" : GDIM, display: "flex", alignItems: "center", justifyContent: "center" }}>🎤</button>
                <button onClick={() => sendMsg()} style={{ width: 32, height: 32, borderRadius: "50%", border: `1px solid rgba(201,168,76,.3)`, background: "linear-gradient(135deg,rgba(201,168,76,.22),rgba(201,168,76,.1))", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: GOLD2 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
                </button>
              </div>
            </div>
            <div style={{ fontSize: 10, color: MU, letterSpacing: "0.05em", marginTop: 8, textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
              <span>ENTER to send</span>
              <span>•</span>
              <span>🎤 Click mic to speak</span>
              <span>•</span>
              <span>🔊 Toggle voice for spoken responses</span>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", background: OB }}>
          <div style={{ padding: "14px 22px", borderBottom: "1px solid rgba(201,168,76,.08)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "rgba(10,10,15,.95)", flexShrink: 0 }}>
            <div>
              <div style={{ fontSize: 14, letterSpacing: "0.12em", color: WH2, fontWeight: 400 }}>{activeNav}</div>
              <div style={{ fontSize: 9, letterSpacing: "0.08em", color: MU, marginTop: 2 }}>ORA by AUREM — Business AI</div>
            </div>
            <button onClick={() => setActiveNav("AI Conversation")} style={{ padding: "6px 14px", background: "transparent", border: `1px solid rgba(201,168,76,.2)`, borderRadius: 6, color: GOLD, fontSize: 10, cursor: "pointer", letterSpacing: "0.05em" }}>← Back to AI</button>
          </div>
          <div style={{ flex: 1, overflowY: "auto" }}>
            {renderMainContent()}
          </div>
        </div>
      )}

      {/* RIGHT PANEL */}
      <div style={{ background: OB2, borderLeft: "1px solid rgba(201,168,76,.1)", padding: "18px 15px", display: "flex", flexDirection: "column", gap: 18, overflowY: "auto" }}>
        <div>
          <div style={{ fontSize: 8, letterSpacing: "0.28em", color: GDIM, marginBottom: 10 }}>PLATFORM METRICS</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 7 }}>
            {[{ val: metrics.queries.toLocaleString(), label: "QUERIES TODAY", trend: "↑ 12%" }, { val: "98.4%", label: "UPTIME", trend: "↑ Stable" }, { val: metrics.response, label: "AVG RESPONSE", trend: "↓ Faster" }, { val: metrics.brands, label: "ACTIVE BRANDS", trend: "↑ Growing" }].map(({ val, label, trend }) => (
              <div key={label} style={{ padding: "10px 9px", border: "1px solid rgba(201,168,76,.08)", borderRadius: 7, background: OB3 }}>
                <div style={{ fontFamily: "monospace", fontSize: 16, color: GOLD2, lineHeight: 1, marginBottom: 3 }}>{val}</div>
                <div style={{ fontSize: 8, color: MU, letterSpacing: "0.07em" }}>{label}</div>
                <div style={{ fontSize: 8, color: "#4ade80", marginTop: 2 }}>{trend}</div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 8, letterSpacing: "0.28em", color: GDIM, marginBottom: 10 }}>AGENT SWARM STATUS</div>
          {agents.map(({ name, status, color }) => (
            <div key={name} style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 9px", border: "1px solid rgba(201,168,76,.06)", borderRadius: 6, marginBottom: 5 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: color !== GDIM ? `0 0 7px ${color}` : "none", animation: color === "#4ade80" ? "pulse 2s infinite" : "none", flexShrink: 0 }} />
              <div style={{ fontSize: 11, color: WH2, flex: 1 }}>{name}</div>
              <div style={{ fontSize: 9, color: MU, letterSpacing: "0.04em" }}>{status}</div>
            </div>
          ))}
        </div>

        <div>
          <div style={{ fontSize: 8, letterSpacing: "0.28em", color: GDIM, marginBottom: 10 }}>CAPABILITIES</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {["AUTOMATION","CRM AI","WHATSAPP","ANALYTICS","MULTI-AGENT","VOICE AI","API OPS","GROWTH","LLM ROUTING","REPORTING"].map(cap => (
              <div key={cap} style={{ padding: "3px 8px", border: "1px solid rgba(201,168,76,.14)", borderRadius: 20, fontSize: 8, letterSpacing: "0.07em", color: SV, background: "rgba(201,168,76,.04)" }}>{cap}</div>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 8, letterSpacing: "0.28em", color: GDIM, marginBottom: 10 }}>LIVE ACTIVITY</div>
          {(liveActivities.length > 0 ? liveActivities : [
            { id: 1, type: "agent", description: "Scout completed market analysis for 3 brands", timestamp: new Date(Date.now() - 120000).toISOString() },
            { id: 2, type: "flow", description: "WhatsApp flow triggered — 847 messages sent", timestamp: new Date(Date.now() - 480000).toISOString() },
            { id: 3, type: "agent", description: "Architect built new automation pipeline", timestamp: new Date(Date.now() - 1380000).toISOString() },
            { id: 4, type: "system", description: "Circuit breaker reset — all systems clear", timestamp: new Date(Date.now() - 3600000).toISOString() },
            { id: 5, type: "onboard", description: "New enterprise brand onboarded", timestamp: new Date(Date.now() - 7200000).toISOString() }
          ]).slice(0, 5).map((activity) => {
            const icon = activity.type === "agent" ? "⚡" : activity.type === "flow" ? "◎" : activity.type === "system" ? "⬡" : "✦";
            const time = activity.timestamp ? (() => {
              const diff = Math.floor((Date.now() - new Date(activity.timestamp).getTime()) / 1000);
              if (diff < 60) return "just now";
              if (diff < 3600) return `${Math.floor(diff/60)} min ago`;
              return `${Math.floor(diff/3600)} hr ago`;
            })() : "";
            return (
              <div key={activity.id} style={{ display: "flex", gap: 8, padding: "7px 0", borderBottom: "1px solid rgba(201,168,76,.05)", animation: "fadeIn 0.3s ease" }}>
                <div style={{ fontSize: 11, flexShrink: 0 }}>{icon}</div>
                <div>
                  <div style={{ fontSize: 10, color: SV, lineHeight: 1.5 }}>{activity.description}</div>
                  <div style={{ fontSize: 9, color: MU, marginTop: 2 }}>{time}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
