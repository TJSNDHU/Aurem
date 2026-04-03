# AUREM - B2B AI SaaS Platform

## Overview

AUREM is an enterprise-grade B2B AI platform featuring **ORA**, an intelligent AI assistant, alongside a comprehensive suite of sales automation, multi-channel outreach, and business intelligence tools.

---

## Architecture

```
AUREM Platform
├── ORA (AI Assistant Interface)
├── Brain Orchestrator (Multi-Agent Coordinator)
├── Scout (Discovery & Research)
├── Architect (Campaign Planning)
├── Envoy (Multi-Channel Outreach)
├── Closer (Deal Finalization)
└── Unified Inbox (Communication Hub)
```

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+
- MongoDB 6+
- Redis (optional, for caching)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start server
python server.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
# or: yarn install

# Start development server
npm start
# or: yarn start
```

---

## Key Features

### ORA - AI Assistant
- Natural language interface
- Voice-to-text input (coming soon: full voice-to-voice)
- Dynamic greetings based on time & weather
- Business intelligence queries

### Multi-Agent System
- **Scout**: Web research, OSINT, company discovery
- **Architect**: Campaign design, workflow automation
- **Envoy**: Email, WhatsApp, Voice, SMS outreach
- **Closer**: Proposals, contracts, payments

### Admin Dashboard
- Real-time analytics
- Customer management
- Campaign monitoring
- Unified communication inbox

---

## Folder Structure

```
AUREM-PROJECT/
├── backend/
│   ├── server.py           # Main FastAPI server
│   ├── routers/            # API route handlers
│   ├── routes/             # Additional routes
│   ├── services/           # Business logic
│   │   └── aurem_commercial/  # Core AUREM services
│   ├── models/             # Pydantic models
│   ├── utils/              # Utilities & middleware
│   ├── voice/              # Voice AI module
│   ├── rag/                # RAG knowledge base
│   ├── tests/              # Unit tests
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment template
│
├── frontend/
│   ├── public/             # Static assets
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Main page components
│   │   ├── platform/       # AUREM platform UI
│   │   ├── contexts/       # React contexts
│   │   ├── hooks/          # Custom hooks
│   │   ├── lib/            # Utilities
│   │   └── App.js          # Root component
│   ├── package.json        # Node dependencies
│   └── tailwind.config.js  # Tailwind CSS config
│
├── database/
│   └── schemas.md          # MongoDB schema docs
│
├── docs/
│   ├── AGENTS.md           # Agent architecture
│   ├── PRD.md              # Product requirements
│   ├── CHANGELOG.md        # Version history
│   └── ...
│
└── README.md               # This file
```

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/platform/auth/login` | Admin login |
| POST | `/api/platform/auth/logout` | Admin logout |
| GET | `/api/platform/auth/me` | Get current user |

### ORA AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/aurem/ai/chat` | Send message to ORA |
| GET | `/api/aurem/ai/sessions` | Get chat sessions |

### Agent Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/agent-reach/discover` | Scout company research |
| POST | `/api/action-engine/campaign` | Create campaign |
| POST | `/api/voice/call` | Initiate voice call |
| GET | `/api/inbox/threads` | Get unified inbox |

---

## Environment Variables

See `backend/.env.example` for complete list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_URL` | Yes | MongoDB connection string |
| `EMERGENT_LLM_KEY` | Yes | Universal LLM API key |
| `JWT_SECRET` | Yes | JWT signing secret |
| `AUREM_ENCRYPTION_KEY` | Yes | Data encryption key |

---

## Testing

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm test
```

---

## Deployment

### Docker (Recommended)

```bash
docker-compose up -d
```

### Manual

1. Set up MongoDB and Redis
2. Configure `.env` files
3. Build frontend: `cd frontend && npm run build`
4. Start backend: `cd backend && python server.py`
5. Serve frontend via nginx or similar

---

## Security

- All API routes require JWT authentication
- Sensitive data encrypted with AES-256
- Rate limiting on all endpoints
- RBAC for admin operations
- Audit logging for compliance

---

## License

Proprietary - All Rights Reserved

---

## Support

For technical support or questions, contact the AUREM team.
