# AUREM

**The Autonomous Business Operating System for Canadian SMBs.**

Outreach · Auto-built Websites · CASL-compliant SMS/Email · Voice AI · Self-healing infrastructure.

Live: **[aurem.live](https://aurem.live)**

---

## What AUREM does in one paragraph

You give AUREM your business (dental clinic, salon, contractor, etc.). It scouts leads from the open web + Apollo, writes personalised cold emails / SMS / WhatsApp / AI voice calls, books appointments, monitors the customer's website for uptime + SEO drift, auto-repairs broken pages, generates board-ready P&L reports, and pays out to Stripe — all without the founder lifting a finger. The system runs 50+ scheduled agents, has zero mocks in production, and rebuilds parts of itself when they break.

---

## Architecture at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  CLOUDFLARE → EMERGENT INGRESS → uvicorn (FastAPI :8001)    │
│                                                             │
│  HealthProbeMiddleware (instant /health + /api/ready)       │
│  FloodGate (token-bucket sentinel + heartbeat protection)   │
│                                                             │
│  FastAPI Router Registry — 145+ routers, organised by:      │
│     /api/admin/*       founder cockpit (33 sidebar items)   │
│     /api/ora/*         5 ORA agent surfaces                 │
│     /api/customer/*    customer-facing surfaces             │
│     /api/v1/public/*   commercialised public API            │
│     /api/scout/*       lead discovery (Apollo + Tavily)     │
│     /api/aurem/*       Stripe billing & subscriptions       │
│     /api/voice/*       Vapi + Retell AI voice               │
│                                                             │
│  Services Layer                                             │
│     • LLM gateway → OpenRouter (Emergent Universal Key)     │
│     • Mongo Atlas (55 collections, all reachable)           │
│     • APScheduler (50+ cron workers across 4 pillars)       │
│     • CTO Skills system (read_codebase / web_search /       │
│       fetch_url / edit_file / run_tests / remember / ...)   │
│     • Live Codebase Health analyzer (every 6h)              │
│                                                             │
│  External integrations (all live, all real)                 │
│     OpenRouter · Apollo · Stripe (LIVE) · Resend · Tavily   │
│     Twilio SMS · WHAPI · Retell AI Voice · Telegram         │
│     Shopify OAuth · GitHub                                  │
└─────────────────────────────────────────────────────────────┘

         Frontend (React SPA, 200+ pages, 162 routes)
            ↑                                ↑
        Admin Shell                    Customer Shell
   (32 sidebar items, 6 sections)    /me, /customer, /dashboard
```

---

## Pillar Health (live telemetry)

AUREM is organised into 4 self-supervised pillars. Each pillar runs its own
schedulers and exposes its health to the founder dashboard at `/admin/pillars-map`.

| Pillar          | Live workers | Collections | Notes                                |
|-----------------|--------------|-------------|--------------------------------------|
| P1 Sales        | 12           | 12 / 12     | Apollo · Auto-Blast · Closer · Scout |
| P2 Billing      | 3            | 12 / 12     | Stripe LIVE · trial drip · win-back  |
| P3 Monitor      | 3            | 12 / 12     | Site uptime · Sentinel · Shannon     |
| P4 Command Hub  | 32           | 19 / 19     | ORA · Memoir · CTO Skills · BugCatch |
| **Total**       | **50 live**  | **55 / 55** | 🟢 system healthy, 0 silent failures |

---

## Repository structure

```
/app
├── backend/                        FastAPI + Mongo + schedulers
│   ├── server.py                   ASGI entry, lifespan, lifecycle
│   ├── routers/                    417 router modules
│   │   ├── registry.py             central include_router pipeline
│   │   ├── pillars_map_router.py   live system telemetry
│   │   ├── codebase_health_router  D-70 live code analyzer
│   │   ├── web_search_router       D-64 Tavily search REST API
│   │   ├── feature_flags_router    D-63 per-tenant rollout flags
│   │   └── …
│   ├── services/                   522 service modules
│   │   ├── ora_council.py          multi-agent verdicts
│   │   ├── codebase_health.py      D-70 analyzer engine
│   │   ├── feature_flags.py        D-63 Mongo-backed flag store
│   │   ├── self_audit.py           hourly aurem.live self-test
│   │   └── …
│   ├── cto_skills/                 LLM-invocable skills
│   │   ├── tavily_search.py        web_search · fetch_url · summarize
│   │   ├── apollo_lead_search.py   B2B lead discovery
│   │   ├── read_codebase.py        AST + file walker
│   │   ├── edit_file.py            search/replace under audit
│   │   └── …
│   ├── pillars/                    P1-P4 pillar workers
│   ├── middleware/                 health_probe · floodgate · audit
│   ├── tools/                      CLI utilities
│   └── tests/                      418 pytest files
│
├── frontend/                       React SPA (CRA)
│   └── src/
│       ├── App.js                  162 routes, no nested router
│       ├── platform/               admin + customer pages (200+ jsx)
│       │   ├── AdminShell.jsx      32-item sidebar, 6 sections
│       │   ├── AdminPillarsMap.jsx live pillar telemetry
│       │   ├── AdminCodebaseHealth D-70 dashboard
│       │   ├── OraDevConsole.jsx   proposal review queue
│       │   ├── BugCatchWidget.jsx  native bug capture
│       │   └── …
│       ├── components/ui/          shadcn/ui (Lucide icons)
│       └── lib/
│           ├── useReliableSSE.js   D-63 SSE reconnect hook
│           └── BuildBadge.jsx      live build SHA chip
│
├── memory/                         documentation that grows
│   ├── PRD.md                      original problem statement
│   ├── CHANGELOG.md                every iter logged
│   ├── ARCHITECTURE.md             deep dive
│   ├── MIGRATION_RULES.md          D-63 zero-downtime rules
│   ├── SYSTEM_AUDIT_2026-06-04.md  full mock + dead-code audit
│   ├── CAMPAIGN_HEALTH_2026-06-04  per-day operational snapshot
│   └── test_credentials.md         founder/admin test accounts
│
└── .emergent/                      platform metadata (do not edit)
```

---

## Zero-mocks policy

Production AUREM contains **zero mocked data paths**. Every integration:

- ✅ Either makes a real API call to the live service
- ✅ Or raises HTTP 503 / `RuntimeError` with the exact missing env var
- ❌ Never returns fake numbers / placeholder data / "scaffold mode" content

Audit log: see `memory/SYSTEM_AUDIT_2026-06-04.md` for the iter-by-iter
mock-purge history (8 mock families removed across D-58 → D-61).

---

## Codebase Health (live, auto-updating)

`GET /api/admin/codebase-health/latest` — auto-refreshes every 30s on the
dashboard, full analyzer re-runs every 6h + on every backend restart.

Snapshot from 2026-06-05:

```
backend totals: 1,240 files · 385,005 lines
size buckets:   ≥1500=13  800-1499=45  300-799=418  safe=764
god files:      3 (top: registry.py imports 231 modules)
circular:       5 detected
top action:     routers/registry.py — 4340 lines, imports 231 modules
CC=483 register_all_routers
health score:   0.0 / 10 (honest — we know what to refactor next)
```

The analyzer is brutally honest. It surfaces the next refactor without anyone
having to discover it manually.

---

## Tech stack

**Backend**
- Python 3.11 · FastAPI · Uvicorn · Motor (async Mongo)
- APScheduler · Pydantic v2 · httpx · radon · jose JWT · passlib

**Frontend**
- React 19 · React Router v7 · Tailwind v3 · shadcn/ui · Lucide icons
- Motion (animations) · framer-motion · sonner (toasts)

**Infra**
- MongoDB Atlas (production) · MongoDB local (preview)
- Emergent native deployment → Kubernetes
- Cloudflare CDN/edge
- Stripe (live keys) · Resend · Twilio · Apollo · Tavily · Retell AI · WHAPI

---

## Quick start (developers)

```bash
# Backend
cd /app/backend
pip install -r requirements.txt
sudo supervisorctl restart backend

# Frontend
cd /app/frontend
yarn install
sudo supervisorctl restart frontend

# Run the full pytest suite
cd /app/backend
python -m pytest tests/ -q
```

Environment variables expected in `backend/.env`:

```
MONGO_URL=mongodb+srv://...
DB_NAME=aurem
JWT_SECRET=...
EMERGENT_LLM_KEY=...
TAVILY_API_KEY=...
APOLLO_API_KEY=...
STRIPE_SECRET_KEY=sk_live_...
RESEND_API_KEY=re_...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
RETELL_API_KEY=...
RETELL_FROM_NUMBER=+1...
RETELL_AGENT_ID=...
TELEGRAM_BOT_TOKEN=...
AUREM_ENCRYPTION_KEY=...
```

Frontend reads only `REACT_APP_BACKEND_URL` from `frontend/.env`.

---

## Key features (founder-facing)

| Feature                  | Where in the app                      |
|--------------------------|---------------------------------------|
| Live system telemetry    | `/admin/pillars-map`                  |
| Codebase health          | `/admin/codebase-health` (auto)       |
| Campaign health          | `/admin/campaign-health` (autofix)    |
| ORA chat (admin)         | `/admin/ora` (CTO + Console tabs)     |
| Web search (Tavily)      | `/admin/web/search` or ORA chat       |
| Auto-build websites      | `/admin/awb-cockpit`                  |
| Stem-Fix queue           | embedded in Pillars Map               |
| Self-Repair Loop         | embedded in Pillars Map               |
| Boardroom P&L            | `/admin/boardroom`                    |
| Feature flags            | `/admin/feature-flags`                |
| ORA Dev Console          | `/admin/ora-dev`                      |
| Memoir (Git-versioned KV)| `/admin/memoir`                       |
| Customer health          | `/admin/customer-health`              |
| Bug capture widget       | floating on every admin page          |

---

## Test coverage

418 pytest files. Every code-level fix from iter D-61 through D-70 is
guarded by a regression test:

| Iter   | What it locks in                                              |
|--------|---------------------------------------------------------------|
| D-61   | mock purges (shopify scaffold, pageindex, label fixes)        |
| D-62   | ORA Dev orphan-proposal filter + cleanup                      |
| D-63   | zero-downtime probe + scheduler graceful shutdown + flags     |
| D-64   | Tavily web search skills + URL fetch + internal-URL blocklist |
| D-65   | scheduler coroutine-wrap fix (8 silent failures resolved)     |
| D-66   | campaign health real fixes (4 yellows → green)                |
| D-67   | Retell voice channel + engagement summary                     |
| D-68   | sidebar dedupe round 1                                        |
| D-69   | sidebar dedupe round 2                                        |
| D-70   | live codebase health analyzer                                 |

Combined: **95/95 PASS** on every commit.

---

## License

Proprietary. Founder: teji.ss1986@gmail.com.
Commercial use requires written permission.

---

*Last updated: 2026-06-05 · iter D-70*
