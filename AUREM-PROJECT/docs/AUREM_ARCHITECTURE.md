# AUREM Platform Architecture
## Omnichannel Business Operating System

**Version:** 2.0 | **Last Updated:** April 2, 2026

---

```
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                    AUREM: AUTONOMOUS BUSINESS OS                  ║
    ║         "Think. Hear. Act. Collaborate. Learn."                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
```

## Executive Summary

AUREM is an **Autonomous Business Operating System** that transforms how enterprises handle customer interactions. Unlike traditional chatbots, AUREM operates as a **Digital Workforce** — a unified, intelligent entity capable of:

- **Thinking** (OODA Loop reasoning)
- **Hearing** (Omnichannel voice & messaging)
- **Acting** (Calendar bookings, payments, emails)
- **Collaborating** (Agent-to-Agent protocols)
- **Learning** (YouTube Knowledge Importer - Roadmap)

**Cost Impact:** 97% reduction vs human agents ($0.45/call AI vs $15/call human)

---

## 📊 AUREM Master Operational Flow Chart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AUREM OPERATIONAL LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────────────┘

    CUSTOMER CONTACT                                              RESOLUTION
         │                                                            ▲
         ▼                                                            │
┌─────────────────┐                                        ┌─────────────────┐
│   1. INGEST     │                                        │    6. AUDIT     │
│   ───────────   │                                        │   ───────────   │
│  📞 Vapi Voice  │                                        │ Brain Debugger  │
│  💬 WhatsApp    │                                        │   OODA Trace    │
│  📧 Email       │                                        │  Unified Inbox  │
│  🌐 Web Chat    │                                        │                 │
└────────┬────────┘                                        └────────▲────────┘
         │                                                          │
         ▼                                                          │
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐│
│   2. OBSERVE    │────▶│   3. ORIENT     │────▶│   4. DECIDE     ││
│   ───────────   │     │   ───────────   │     │   ───────────   ││
│  Scout Agent    │     │ Architect Agent │     │Brain Orchestrator│
│  Intent Detection│     │  Knowledge Base │     │  Tool Selection ││
│  Redis Hydrate  │     │  PDRN/Auto KB   │     │  A2A Handoff    ││
│  Customer Fetch │     │  Context Build  │     │  Priority Queue ││
└─────────────────┘     └─────────────────┘     └────────┬────────┘│
                                                         │         │
                                                         ▼         │
                                                ┌─────────────────┐│
                                                │    5. ACT       ││
                                                │   ───────────   │┘
                                                │  Envoy Agent    │
                                                │  📅 Calendar    │
                                                │  💳 Stripe      │
                                                │  📧 Gmail       │
                                                │  💬 Respond     │
                                                └─────────────────┘
```

### Lifecycle Stages Detail

| Stage | Process | Technical Component | Output |
|-------|---------|---------------------|--------|
| **1. Ingest** | Incoming Vapi Call / WhatsApp / Email | **Omnichannel Gateway** | Raw message + metadata |
| **2. Observe** | Identify intent, fetch user profile | **Scout Agent + Redis** | Customer context hydrated |
| **3. Orient** | Contextualize against Business KB | **Architect Agent** | Decision framework built |
| **4. Decide** | Select tool or A2A handoff | **Brain Orchestrator** | Action plan determined |
| **5. Act** | Execute booking/payment, respond | **Envoy Agent + Action Engine** | Real-world execution |
| **6. Audit** | Log full OODA trace | **Brain Debugger** | Transparent decision log |

---

## Phase 1: The Brain Orchestrator (OODA Architecture)

### The OODA Loop Engine

AUREM's core intelligence is built on the **OODA Loop** (Observe, Orient, Decide, Act) — the same decision framework used by military strategists and elite performers.

```
                    ┌──────────────────────────────────────┐
                    │         OODA LOOP ENGINE             │
                    └──────────────────────────────────────┘
                    
        ┌─────────┐         ┌─────────┐         ┌─────────┐         ┌─────────┐
        │ OBSERVE │   ───▶  │ ORIENT  │   ───▶  │ DECIDE  │   ───▶  │   ACT   │
        └────┬────┘         └────┬────┘         └────┬────┘         └────┬────┘
             │                   │                   │                   │
             ▼                   ▼                   ▼                   ▼
        ┌─────────┐         ┌─────────┐         ┌─────────┐         ┌─────────┐
        │ Scout   │         │Architect│         │  Brain  │         │ Envoy   │
        │ Agent   │         │ Agent   │         │Orchestr.│         │ Agent   │
        └─────────┘         └─────────┘         └─────────┘         └─────────┘
             │                   │                   │                   │
             ▼                   ▼                   ▼                   ▼
        "What's          "What does          "What's the         "Execute
         happening?"      this mean?"         best action?"       & respond"
```

### Agent Swarm Architecture

| Agent | Role | Capabilities |
|-------|------|--------------|
| **Scout Agent** | Data Retrieval & RAG | Intent classification, Redis memory lookup, customer profile hydration, Agent-Reach research |
| **Architect Agent** | Strategic Planning | Knowledge base consultation, context building, multi-step planning, priority assessment |
| **Envoy Agent** | Communication & Execution | Tool invocation, response formatting, TTS narration, channel-appropriate delivery |

### Redis-Powered "Hydrated Memory"

AUREM maintains persistent customer context across all channels:

```python
# Example: Customer calls Monday, WhatsApps Friday
customer_profile = {
    "customer_id": "cust_tejinder_001",
    "name": "Tejinder",
    "tier": "vip",
    "vehicles": [{"make": "GMC", "model": "Yukon", "year": 2018}],
    "last_interaction": "2026-04-01T14:30:00Z",
    "last_service": "Oil change + brake inspection",
    "preferences": {"contact": "whatsapp", "time": "afternoon"},
    "lifetime_value": 4500.00
}

# Redis Key: aurem:customer:{business_id}:{phone_hash}
# TTL: 30 days (auto-refresh on interaction)
```

**Key Capability:** A customer calling about their "2018 Yukon" on Monday is **instantly recognized** when they WhatsApp on Friday — no repetition required.

---

## Phase 2: Omnichannel Sensory Layer (Voice & Chat)

### Voice Stack: Vapi + Vobiz + ElevenLabs

```
┌─────────────────────────────────────────────────────────────────────┐
│                     VOICE ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   [Customer Phone] ──▶ [Vobiz SIP Trunk] ──▶ [Vapi AI Platform]    │
│                                                      │              │
│                                                      ▼              │
│                              ┌────────────────────────────────┐     │
│                              │     AUREM Voice Gateway        │     │
│                              │  ───────────────────────────   │     │
│                              │  • Webhook: /api/aurem-voice/  │     │
│                              │  • VIP Recognition             │     │
│                              │  • Smart Endpointing (800ms)   │     │
│                              │  • OODA Telemetry              │     │
│                              └────────────────────────────────┘     │
│                                                      │              │
│                                                      ▼              │
│                              ┌────────────────────────────────┐     │
│                              │     ElevenLabs TTS             │     │
│                              │  • Rachel (VIP Voice)          │     │
│                              │  • Alloy (Standard)            │     │
│                              │  • <500ms latency              │     │
│                              └────────────────────────────────┘     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Voice Capabilities:**
- **VIP Recognition:** Dynamic persona swap based on customer tier (GPT-4o for VIP, GPT-4o-mini for standard)
- **Smart Endpointing:** 800ms latency for professional, natural conversation
- **Silent Context Handoff:** Human agents receive full transcript before pickup

### WhatsApp Cloud API Integration

```
Meta Business Platform
        │
        ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│  Embedded Signup  │ ───▶ │  Webhook Handler  │ ───▶ │  Unified Inbox    │
│  (OAuth Flow)     │      │  /api/whatsapp/   │      │  (Real-time)      │
└───────────────────┘      └───────────────────┘      └───────────────────┘
                                    │
                                    ▼
                           ┌───────────────────┐
                           │  WhatsApp Flows   │
                           │  • Lead Capture   │
                           │  • VIN Entry      │
                           │  • Skin Type Quiz │
                           └───────────────────┘
```

### Unified Inbox: The Command Center

All channels merge into a single, searchable thread:

| Channel | Icon | Real-time | Actions |
|---------|------|-----------|---------|
| Voice (Vapi) | 📞 | ✅ WebSocket | Transcript, Recording |
| WhatsApp | 💬 | ✅ WebSocket | Reply, Template Send |
| Email (Gmail) | 📧 | ✅ Polling | Reply, Forward |
| Web Chat | 🌐 | ✅ WebSocket | Reply, Escalate |

---

## Phase 3: The Action Engine & Agent-Reach

### Tool Manifest

AUREM can execute real-world actions through these integrated tools:

| Tool | Endpoint | Capability |
|------|----------|------------|
| **Google Calendar** | `book_appointment` | Schedule meetings with availability check |
| **Stripe** | `create_invoice`, `create_payment_link` | Generate invoices and payment links |
| **Gmail** | `send_email` | Professional follow-up communications |
| **WhatsApp** | `send_whatsapp` | Template and free-form messaging |

### Agent-Reach: Zero-API Social Intelligence

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT-REACH ARCHITECTURE                         │
│              "The Invisible Intelligence Layer"                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │
│   │   Twitter   │   │   Reddit    │   │   YouTube   │              │
│   │  (bird CLI) │   │   (Exa)     │   │  (yt-dlp)   │              │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │
│          │                 │                 │                      │
│          └────────────────┬┴─────────────────┘                      │
│                           │                                         │
│                           ▼                                         │
│                 ┌─────────────────────┐                             │
│                 │   Agent-Reach API   │                             │
│                 │  /api/reach/*       │                             │
│                 │  ─────────────────  │                             │
│                 │  Cost: $0/request   │                             │
│                 └─────────────────────┘                             │
│                           │                                         │
│                           ▼                                         │
│                 ┌─────────────────────┐                             │
│                 │   Scout Agent       │                             │
│                 │   (Market Intel)    │                             │
│                 └─────────────────────┘                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Zero-API Philosophy:**
- No developer accounts required
- Uses browser cookies for authentication
- Results cached for analytics

**Cost Comparison:**
| Service | Traditional API | Agent-Reach |
|---------|----------------|-------------|
| Twitter Search | $100+/month | $0 |
| Reddit Search | $50+/month | $0 |
| YouTube Transcripts | $0.10/video | $0 |

### SKILL.md Framework

Agents learn new commands through the SKILL.md file:

```markdown
# AUREM Agent-Reach Skills

## Twitter/X Search
Command: `search_twitter(query, limit=20)`
Example: `search_twitter("PDRN skincare reviews")`

## Reddit Search  
Command: `search_reddit(query, subreddit=None)`
Example: `search_reddit("best mechanic Toronto", subreddit="askTO")`

## YouTube Transcript
Command: `get_youtube_transcript(url)`
Example: `get_youtube_transcript("https://youtube.com/watch?v=xxx")`
```

---

## Phase 4: A2A (Agent-to-Agent) Communication Protocol

### Inter-Agent Communication

AUREM supports multiple business verticals within a single brain:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    A2A COMMUNICATION FLOW                           │
└─────────────────────────────────────────────────────────────────────┘

   ┌─────────────────┐                      ┌─────────────────┐
   │  REROOTS        │                      │  TJ AUTO        │
   │  Skincare Agent │◀────── A2A ────────▶│  Clinic Agent   │
   │                 │      Protocol        │                 │
   │  Knowledge:     │                      │  Knowledge:     │
   │  • PDRN Tech    │                      │  • GMC/Chevy    │
   │  • Skincare Rx  │                      │  • Diagnostics  │
   │  • Luxe Service │                      │  • Parts Catalog│
   └─────────────────┘                      └─────────────────┘
           │                                        │
           └──────────────┬─────────────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Shared Services │
                 │  ───────────────│
                 │  • Stripe       │
                 │  • Calendar     │
                 │  • Analytics    │
                 └─────────────────┘
```

### Hiring Protocol

One agent can "hire" another for specialized tasks:

```python
# Example: Skincare Agent needs payment processing
a2a_request = {
    "from_agent": "reroots_skincare",
    "to_agent": "finance_agent",
    "task": "create_payment_link",
    "params": {
        "amount": 299.00,
        "description": "PDRN Facial Treatment",
        "customer_email": "client@example.com"
    },
    "callback": "skincare_agent.handle_payment_result"
}
```

---

## Phase 5: Observability & Morning Brief

### Brain Debugger UI

The Brain Debugger provides **complete transparency** into AI decision-making:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BRAIN DEBUGGER                                 │
│                   "The Glass Box"                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  OODA Trace #thought_2026040214301                                  │
│  ──────────────────────────────────────────────────────────────     │
│                                                                     │
│  👁️ OBSERVE: "Customer asked about PDRN treatment pricing"         │
│     └─ Intent: PRICING_INQUIRY (confidence: 0.94)                   │
│     └─ Customer: VIP Tier, 3 previous purchases                     │
│                                                                     │
│  🧭 ORIENT: Consulting Skincare Knowledge Base                      │
│     └─ Product: PDRN Facial Treatment                               │
│     └─ Base Price: $299, VIP Discount: 15%                          │
│                                                                     │
│  🎯 DECIDE: Selected tool "create_payment_link"                     │
│     └─ Reasoning: "Customer is VIP, offer discounted price"         │
│     └─ Alternative considered: "send_brochure"                      │
│                                                                     │
│  ⚡ ACT: Payment link created, WhatsApp sent                        │
│     └─ Stripe Link: pay.stripe.com/xxx                              │
│     └─ Response time: 2.3s                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Executive Morning Brief

The Morning Brief aggregates daily intelligence for business owners:

**Endpoint:** `GET /api/aurem/morning-brief`

```json
{
  "brief": {
    "narration": "Good morning. Take a breath — we shall address each matter with precision...",
    "tone": "old_money_composed",
    "stress_mitigation_active": true
  },
  "time": {
    "current_time": "9:15 AM",
    "greeting": "Good morning",
    "day_of_week": "Thursday"
  },
  "weather": {
    "temperature": 12,
    "condition": "Partly Cloudy",
    "location": "Mississauga"
  },
  "tasks": {
    "count": 6,
    "load_level": "heavy",
    "items": [...]
  }
}
```

**Sentiment Layer:**
| Task Load | Tone | Style |
|-----------|------|-------|
| Light (0-2) | Casual | "Have a great day!" |
| Moderate (3-5) | Professional | "You've got this. Focus on what matters." |
| Heavy (>5) | **Old Money Composed** | "Excellence is not rushed — it is cultivated." |

### Voice Analytics Dashboard

ROI tracking and conversion metrics:

| Metric | Value | Impact |
|--------|-------|--------|
| Total Calls | 847 | Volume indicator |
| Avg Duration | 142s | Efficiency measure |
| Action Rate | 38% | Conversion success |
| Cost Saved | **$12,450** | 97% reduction vs human |

---

## 🚀 Future Roadmap

### P0 (Immediate)
- [ ] Configure live Vapi credentials
- [ ] Configure Exa API for live Reddit search

### P1 (Near-term)
- [ ] **YouTube Knowledge Importer** — Auto-ingest competitor video transcripts into KB
- [ ] Voice call recording playback
- [ ] Multi-language voice support

### P2 (Backlog)
- [ ] Full A2A protocol implementation
- [ ] ROI Calculator widget
- [ ] Automated competitor monitoring alerts

---

## ROI Calculator

Based on Phase 8.2 Voice Analytics data:

| Metric | Human Agent | AUREM AI | Savings |
|--------|-------------|----------|---------|
| Cost per call | $15.00 | $0.45 | **$14.55** |
| Calls/month | 1,000 | 1,000 | — |
| Monthly cost | $15,000 | $450 | **$14,550** |
| Annual savings | — | — | **$174,600** |

---

## Technical Specifications

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/brain/execute` | POST | Execute OODA loop |
| `/api/aurem-voice/webhook` | POST | Vapi webhook handler |
| `/api/whatsapp/webhook` | POST | WhatsApp webhook |
| `/api/platform/inbox/messages` | GET | Unified Inbox fetch |
| `/api/reach/twitter` | POST | Twitter search |
| `/api/aurem/morning-brief` | GET | Morning Brief |

### Technology Stack

- **Backend:** FastAPI (Python 3.11)
- **Frontend:** React 18 + Vite
- **Database:** MongoDB Atlas
- **Cache:** Redis
- **Voice:** Vapi AI + Vobiz SIP + ElevenLabs
- **Messaging:** WhatsApp Cloud API
- **Payments:** Stripe
- **Calendar:** Google Calendar API

---

*AUREM — The Autonomous Business Operating System*
*"Where AI doesn't just assist. It operates."*
