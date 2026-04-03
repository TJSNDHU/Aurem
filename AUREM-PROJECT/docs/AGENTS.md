# AUREM AI Agent Architecture

## Overview

AUREM is a B2B AI SaaS platform featuring multiple specialized AI agents that work together through an orchestrated system. This document describes the agent hierarchy, their roles, and how they interact.

---

## Agent Hierarchy

```
                    ┌─────────────────────────┐
                    │    BRAIN ORCHESTRATOR   │
                    │   (Master Controller)   │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│     SCOUT     │     │   ARCHITECT   │     │     ENVOY     │
│  (Discovery)  │     │   (Planning)  │     │  (Outreach)   │
└───────────────┘     └───────────────┘     └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │        CLOSER           │
                    │   (Deal Execution)      │
                    └─────────────────────────┘
```

---

## Core Agents

### 1. Brain Orchestrator (`brain_orchestrator.py`)
**Role**: Master coordinator for all AI agents

**Responsibilities**:
- Routes tasks to appropriate specialized agents
- Manages multi-turn conversations with context retention
- Handles agent-to-agent (A2A) handoffs
- Enforces rate limiting and circuit breakers
- Maintains conversation memory via Redis

**Key Features**:
- Semantic caching for repeated queries
- Automatic fallback handling
- Cross-agent communication protocol

**Location**: `/backend/services/aurem_commercial/brain_orchestrator.py`

---

### 2. Scout Agent (`agent_reach.py`)
**Role**: Discovery and research intelligence

**Responsibilities**:
- Web research and OSINT gathering
- Company and contact discovery
- Market intelligence collection
- Social media profile analysis
- YouTube knowledge extraction

**Capabilities**:
- Deep web searching
- LinkedIn profile parsing
- News aggregation
- Competitor analysis

**Location**: `/backend/services/aurem_commercial/agent_reach.py`

---

### 3. Architect Agent (`action_engine.py`)
**Role**: Strategic planning and campaign design

**Responsibilities**:
- Campaign structure creation
- Workflow automation design
- Message sequence planning
- A/B testing setup
- Performance metric definition

**Outputs**:
- Campaign blueprints
- Automation workflows
- Personalization templates

**Location**: `/backend/services/aurem_commercial/action_engine.py`

---

### 4. Envoy Agent (`voice_service.py`, `whatsapp_service.py`)
**Role**: Multi-channel outreach execution

**Responsibilities**:
- Email campaign execution
- WhatsApp messaging
- Voice call initiation (OmniDim)
- SMS alerts
- Social media outreach

**Supported Channels**:
- Email (Resend)
- WhatsApp (Cloud API / WHAPI)
- Voice (Twilio / OmniDim)
- SMS (Twilio)

**Location**: `/backend/services/aurem_commercial/`

---

### 5. Closer Agent (`billing_service.py`)
**Role**: Deal finalization and payment processing

**Responsibilities**:
- Proposal generation
- Contract management
- Payment processing (Stripe, PayPal)
- Invoice automation
- Subscription management

**Features**:
- Multi-currency support
- Recurring billing
- Usage-based metering

**Location**: `/backend/services/aurem_commercial/billing_service.py`

---

## Support Services

### 6. ORA (Customer-Facing AI)
**Role**: Intelligent assistant interface

**Location**: `/frontend/src/platform/AuremAI.jsx`

**Features**:
- Natural language understanding
- Voice-to-text (Whisper)
- Text-to-speech output
- Dynamic greeting based on time/weather
- Real-time business insights

---

### 7. Unified Inbox (`unified_inbox_service.py`)
**Role**: Centralized communication hub

**Aggregates**:
- Email threads
- WhatsApp conversations
- SMS messages
- Voice call logs
- Chat transcripts

**Location**: `/backend/services/aurem_commercial/unified_inbox_service.py`

---

### 8. A2A Handoff Service (`a2a_handoff_service.py`)
**Role**: Agent-to-agent communication protocol

**Handles**:
- Context preservation across agents
- Task delegation with full history
- Escalation workflows
- Human-in-the-loop triggers

**Location**: `/backend/services/aurem_commercial/a2a_handoff_service.py`

---

## Router Files (API Endpoints)

| Router | Purpose | Path |
|--------|---------|------|
| `platform_auth_router.py` | Admin authentication | `/api/platform/auth` |
| `aurem_ai_router.py` | ORA AI endpoints | `/api/aurem/ai` |
| `agent_reach_router.py` | Scout operations | `/api/agent-reach` |
| `action_engine_router.py` | Architect workflows | `/api/action-engine` |
| `voice_layer_router.py` | Voice AI calls | `/api/voice` |
| `brain_router.py` | Orchestrator control | `/api/brain` |
| `unified_inbox_router.py` | Inbox aggregation | `/api/inbox` |
| `aurem_billing_router.py` | Payment processing | `/api/billing` |

---

## Middleware & Utils

| File | Purpose |
|------|---------|
| `aurem_security_middleware.py` | Rate limiting, request validation |
| `aurem_encryption.py` | Secure data encryption |
| `aurem_jwt.py` | JWT token management |
| `aurem_rate_limiter.py` | API throttling |
| `circuit_breaker.py` | Fault tolerance |

---

## Database Collections

| Collection | Agent | Purpose |
|------------|-------|---------|
| `platform_users` | Auth | Admin accounts |
| `agent_sessions` | Orchestrator | Conversation memory |
| `campaigns` | Architect | Campaign definitions |
| `outreach_logs` | Envoy | Communication history |
| `deals` | Closer | Deal pipeline |
| `invoices` | Closer | Billing records |
| `audit_logs` | All | Activity tracking |

---

## Configuration

Agents are configured via environment variables and the following files:
- `/backend/config.py` - Core configuration
- `/backend/brands_config.py` - Multi-tenant brand settings
- `/backend/a2a/agent_card.json` - A2A protocol definition

---

## Getting Started

1. Set up environment variables (see `.env.example`)
2. Install dependencies: `pip install -r requirements.txt`
3. Start the backend: `python server.py`
4. Access ORA at `/aurem-ai` (requires admin authentication)

---

## Security Notes

- All agents operate within role-based access controls (RBAC)
- Sensitive data is encrypted at rest and in transit
- API keys are managed via the Key Service with rotation support
- Audit logs track all agent actions for compliance
