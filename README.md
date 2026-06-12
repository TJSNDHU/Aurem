# AUREM

**The Autonomous Business Operating System for Canadian SMBs.**

A self-driving platform that runs the entire customer-acquisition and operations stack for service businesses — outbound prospecting, multi-channel outreach, AI voice calls, auto-built websites, billing, monitoring, and self-repair — without the founder lifting a finger.

Live: **[https://aurem.live](https://aurem.live)** · Preview: internal Emergent K8s

---

## Table of contents

1. [What AUREM does](#what-aurem-does)
2. [Who it is for](#who-it-is-for)
3. [Architecture overview](#architecture-overview)
4. [Pillar Health system](#pillar-health-system)
5. [Repository layout](#repository-layout)
6. [Zero-mocks policy](#zero-mocks-policy)
7. [Codebase Health (live analyzer)](#codebase-health-live-analyzer)
8. [Autonomous Security & Supply-Chain Self-Healing](#autonomous-security--supply-chain-self-healing)
9. [Customer portal (/my)](#customer-portal-my)
10. [Wiring verifier (CI)](#wiring-verifier-ci)
11. [Zero-downtime deploys](#zero-downtime-deploys)
12. [Tech stack](#tech-stack)
13. [Third-party integrations](#third-party-integrations)
14. [Quick start (developers)](#quick-start-developers)
15. [Environment variables](#environment-variables)
16. [Founder-facing features](#founder-facing-features)
17. [Public API (commercialised)](#public-api-commercialised)
18. [Test coverage](#test-coverage)
19. [Known debt](#known-debt)
20. [Conventions & rules](#conventions--rules)
21. [License](#license)

---

## What AUREM does

You connect your business profile (dental clinic, salon, contractor, accountant, real-estate agent, etc.). AUREM then:

1. **Finds your customers** — scouts the open web + Apollo for B2B leads matching your ideal-customer profile.
2. **Talks to them** — writes personalised cold emails, SMS, WhatsApp, or AI voice calls (Retell AI) in your tone. CASL-compliant by design.
3. **Books appointments** — when prospects engage, AUREM handles the back-and-forth and drops calendar invites.
4. **Monitors their world** — uptime, SEO drift, Core Web Vitals, broken images, missing alt-text. Auto-repairs what it can.
5. **Bills automatically** — Stripe-metered usage with live keys, trial drip, win-back campaigns.
6. **Reports to you daily** — board-ready P&L, lead funnel, reply rates, voice call summaries — delivered as a morning brief.
7. **Heals itself** — circuit breakers on every external integration, scheduled self-audits against the live aurem.live site, **autonomous supply-chain security scanning (SAST + secrets + dependency CVEs) with Council-gated auto-fix — no human required**, plus an "ORA Dev Console" where riskier proposed code fixes await your one-click approval.

**Zero mocks in production.** Every dashboard number is sourced from real database queries or live API calls. If an integration is missing, the system raises HTTP 503 with the exact missing env var, never returns fake numbers.

---

## Who it is for

| Persona | Pain AUREM solves |
|---|---|
| **Solo founder of a service business** | Stops the 6 AM cold-email grind. AUREM handles end-to-end outreach. |
| **Operator scaling a multi-location SMB** | One dashboard for every customer's site, billing, and lead pipeline. |
| **Agency reselling automation** | White-label-able admin surface, per-tenant feature flags. |
| **Developer using AUREM's public API** | Pay-per-call access to the ORA agent for chat, search, and orchestration. |

---

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLOUDFLARE  →  EMERGENT INGRESS  →  uvicorn (FastAPI :8001)         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ASGI OUTERMOST                                                │  │
│  │   HealthProbeMiddleware    fast /health + /ready (Mongo-aware) │  │
│  │   FloodGate                token-bucket + heartbeat protection │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  FASTAPI ROUTER REGISTRY  (routers/registry.py, 145+ routers)  │  │
│  │   /api/admin/*       founder cockpit — 9 sidebar groups        │  │
│  │   /api/ora/*         ORA agent surfaces (chat, council, brain) │  │
│  │   /api/customer/*    customer-facing surfaces                  │  │
│  │   /api/v1/public/*   commercialised public API (metered)       │  │
│  │   /api/scout/*       lead discovery (Apollo + Tavily + Ghost)  │  │
│  │   /api/aurem/*       Stripe billing & subscriptions            │  │
│  │   /api/voice/*       Vapi + Retell AI voice                    │  │
│  │   /api/shopify/*     OAuth + Pulse SEO scanner                 │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SERVICES LAYER                                                │  │
│  │   • LLM gateway      OpenRouter (Emergent Universal Key)       │  │
│  │   • MongoDB Atlas    55 collections, all reachable             │  │
│  │   • APScheduler      50+ async workers across 4 pillars        │  │
│  │   • CTO Skills       LLM-invocable tools (see §13)             │  │
│  │   • Codebase Health  every-6h analyzer (see §7)                │  │
│  │   • Feature Flags    Mongo-backed per-tenant rollouts          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  EXTERNAL                                                      │  │
│  │   OpenRouter · Stripe (LIVE) · Apollo · Tavily · Resend        │  │
│  │   Twilio SMS · WHAPI · Retell AI Voice · Telegram · Shopify    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘

         Frontend (React SPA, 375 .jsx files, 162 routes)
            ↑                                ↑
        Admin Shell                    Customer Shell
   (9 sidebar groups)            /my (URL-routed + CustomerGuard)
```

### Why this shape

- **One ASGI entry, one router registry.** No microservices. Every concern lives in one Python process so the founder can debug everything by reading one log file.
- **Pillars own their state.** Each of the 4 pillars (Sales / Billing / Monitor / Command Hub) owns its collections and schedulers. Pillar Map surfaces health per pillar.
- **CTO Skills decouple reasoning from execution.** The LLM emits `[[SKILL: name {args}]]` tokens; a parser dispatches to deterministic Python tools. This is how the system stays explainable.

---

## Pillar Health system

AUREM is structured around 4 self-supervised pillars. Each runs its own scheduled workers and reports health in real time at `/admin/pillars-map`.

| # | Pillar | Workers | Collections | Owns |
|---|---|---|---|---|
| **P1** | **Sales** | 12 | 12 / 12 | Apollo · Auto-Blast · Closer · Scout · Followup · Referral |
| **P2** | **Billing** | 3 | 12 / 12 | Stripe LIVE · Trial drip · Win-back · Compliance |
| **P3** | **Monitor** | 3 | 12 / 12 | Site uptime · Sentinel · Shannon runner |
| **P4** | **Command Hub** | 32 | 19 / 19 | ORA · Memoir · CTO Skills · BugCatch · Daily brief |
| | **Total** | **50** | **55 / 55** | 🟢 0 silent failures |

The map shows every collection, every scheduler, every flow. If a worker hasn't ticked in N minutes, the row turns yellow. If a collection is unreachable, it turns red. The founder always knows what is alive.

---

## Repository layout

```
/app
├── backend/                            FastAPI + Motor + APScheduler
│   ├── server.py                       ASGI entry, lifespan, lifecycle
│   ├── routers/             (417)      every HTTP surface
│   │   ├── registry.py                 central include_router pipeline
│   │   ├── pillars_map_router.py       live system telemetry
│   │   ├── codebase_health_router.py   D-70 live code analyzer
│   │   ├── web_search_router.py        D-64 Tavily search REST API
│   │   ├── feature_flags_router.py     D-63 per-tenant rollout flags
│   │   ├── campaign_health_router.py   campaign-state + autofix
│   │   ├── ora_dev_actions_router.py   proposal review + cleanup
│   │   └── …
│   ├── services/            (522)      business logic, no HTTP
│   │   ├── ora_council.py              multi-agent verdicts (SOC2 trail)
│   │   ├── codebase_health.py          AST + radon analyzer
│   │   ├── feature_flags.py            deterministic per-tenant bucketing
│   │   ├── self_audit.py               hourly aurem.live self-test
│   │   ├── campaign_health.py          13 channel + engagement checks
│   │   ├── self_repair_loop.py         auto-fix scanner (canary 10%)
│   │   └── …
│   ├── cto_skills/                     LLM-invocable skills (D-60+)
│   │   ├── tavily_search.py            web_search · fetch_url · summarize
│   │   ├── apollo_lead_search.py       B2B lead discovery
│   │   ├── read_codebase.py            AST + file walker
│   │   ├── edit_file.py                search/replace under audit
│   │   ├── run_tests.py                pytest invocation
│   │   ├── send_email_via_resend.py    typed outbound mail
│   │   ├── remember.py · recall.py     Memoir read/write
│   │   └── registry.py                 @skill decorator + manifest
│   ├── pillars/                        P1–P4 pillar workers
│   ├── middleware/                     health_probe · floodgate · audit
│   ├── tools/                          CLI utilities
│   └── tests/               (418)      pytest suite
│
├── frontend/                           React SPA (CRA)
│   ├── public/
│   └── src/
│       ├── App.js                      162 routes, single Router
│       ├── platform/        (375)      admin + customer pages
│       │   ├── AdminShell.jsx          9-group sidebar (D-82c), per-section collapse
│       │   ├── admin/AdminSupplyChain.jsx  D-82 security posture cockpit
│       │   ├── customer/CustomerShell.jsx   D-82c guarded /my portal (8 pages)
│       │   ├── AdminPillarsMap.jsx     live telemetry with drill-down
│       │   ├── AdminCodebaseHealth.jsx D-70 dashboard (30s auto-refresh)
│       │   ├── CampaignHealthPage.jsx  D-66 multi-channel health + autofix
│       │   ├── OraDevConsole.jsx       proposal review queue
│       │   ├── BugCatchWidget.jsx      native bug capture (every page)
│       │   ├── AuremDashboard.jsx      customer-facing hub
│       │   └── …
│       ├── components/ui/              shadcn/ui (Lucide icons)
│       └── lib/
│           ├── useReliableSSE.js       D-63 SSE reconnect hook
│           └── BuildBadge.jsx          live build SHA chip
│
├── memory/                             documentation that grows
│   ├── PRD.md                          original problem statement
│   ├── CHANGELOG.md                    every iter logged
│   ├── ARCHITECTURE.md                 deep dive
│   ├── MIGRATION_RULES.md              D-63 zero-downtime rules
│   ├── SYSTEM_AUDIT_2026-06-04.md      full mock + dead-code audit
│   ├── CAMPAIGN_HEALTH_2026-06-04.md   daily operational snapshot
│   └── test_credentials.md             admin test accounts
│
└── .emergent/                          platform metadata (do not edit)
```

**Scale:** 1,667 backend `.py` files (385k lines) · 375 frontend `.jsx` files · 418 pytest files. The codebase health analyzer (§7) is what keeps this navigable.

---

## Zero-mocks policy

Production AUREM contains **zero mocked data paths**. Every integration either:

- ✅ Makes a real API call to the live service
- ✅ Or raises HTTP 503 / `RuntimeError` with the exact missing env var
- ❌ **Never** returns fake numbers, placeholder data, or "scaffold mode" content

Audit log: `memory/SYSTEM_AUDIT_2026-06-04.md` documents the iter-by-iter mock purges (8 mock families removed across iter D-58 → D-61):

- `shopify_pulse_router._scaffold_scan` (fake health scores)
- `pageindex_service` mock returns
- `crm_sync`, `recovery_comms`, `enrichment_service`
- `oracle_proactive`, `proximity_blast`, `toon_stripe_service`
- Stripe label fixes (`"mock"` → `"test"`)

Regression tests in `test_d61_mock_purge.py` ensure removed mocks stay removed.

---

## Codebase Health (live analyzer)

`GET /api/admin/codebase-health/latest` — auto-refreshes every 30 s on the dashboard. Full analyzer re-runs every 6 h **and** on every backend restart.

**Snapshot (2026-06-05, 5.65 s scan):**

```
backend totals:  1,240 files  ·  385,005 lines
size buckets:    ≥1500 = 13   800–1499 = 45   300–799 = 418   safe = 764
god files:       3            (registry.py imports 231 modules)
circular:        5 detected
complexity (top):
  CC=483   routers/registry.py :: register_all_routers
  CC=260   routers/aurem_chat.py :: _aurem_chat_inner
  CC=152   routers/live_scanner.py :: stream_scan
top action:      routers/registry.py  →  "4340 lines, imports 231 modules"
health score:    0.0 / 10   (brutally honest)
```

The analyzer is intentionally harsh. It surfaces the next refactor without anyone having to discover it manually. Implementation: pure-Python AST + `radon` for cyclomatic complexity.

---
## Autonomous Security & Supply-Chain Self-Healing

AUREM dog-foods its own platform: it scans its **own** codebase and dependencies
on the same 6-hour cadence it uses for customer sites, and — via the ORA Council
— **fixes what it safely can without a human in the loop** (iter D-82 / D-82b).

### What it scans (real tools, zero mocks)

Five real scanners run concurrently inside the Pillar-3 worker
(`services/supply_chain_scanner.py`), each shelling out to the genuine CLI and
parsing its real JSON output:

| Layer | Tool | What it catches |
|---|---|---|
| **SAST** (static code) | `bandit` | `eval`, unsafe temp files, weak crypto, injection smells |
| **Secret scanning** | `detect-secrets` (+ `trufflehog` when present) | API keys / tokens / credentials committed to source |
| **SCA — Python deps** | `pip-audit` | Known CVEs in `backend/requirements.txt` |
| **SCA — JS deps** | `yarn audit` | Known CVEs in `frontend/package.json` |

Findings are normalised into one schema, scored into a **posture score**, and
persisted per-tenant (`business_id="aurem_self"`) in `supply_chain_scans`
(history) + `supply_chain_latest` (snapshot). A `notifications` row is raised
whenever critical/high counts regress.

**Baseline sweep (first run):** 285 real findings across all five tools
(1 critical, 210 high, 69 medium) — score `0/10`, brutally honest. These are
mostly outdated CVE-laden dependencies, now being auto-upgraded each cycle.

### How it fixes — ORA Council, no human required

Every finding is routed through the existing **ORA Council** (CASL + QA required
voters, security advisory) — the same trust-but-verify engine Sentinel uses for
runtime errors. Approved remediations are applied **for real, automatically**:

- **`pip` upgrades** (any severity once Council-approved): backup
  `requirements.txt` → real `pip install` → smoke-import → rewrite pin →
  **rollback on any failure**. Proven live: 40 CVEs auto-upgraded in one cycle
  (e.g. `2.10.0 → 2.13.0`), backend stayed healthy throughout.
- **`yarn` upgrades**: backup `package.json` + `yarn.lock` → `yarn upgrade` →
  frozen-lockfile install validation → rollback on failure.
- **Secrets & SAST**: Council-logged but **never auto-rewritten** — a secret must
  be rotated at the provider, and auto-editing source is unsafe. These surface in
  the Sentinel `repair_suggestions` queue, flagged `manual_only`.

Each decision is logged to `supply_chain_remediations` and learned by the ORA
brain (`ora_brain_thoughts`). Council-gated autofix is **on by default**; set
`AUREM_SUPPLY_CHAIN_COUNCIL_AUTOFIX=false` to fall back to suggest-only.

### Relationship to Sentinel

Sentinel (`services/sentinel_repair_loop.py`) is **reactive** — it heals runtime
errors (frontend JS exceptions, backend log crashes) after they happen. The
supply-chain scanner is **proactive** — it closes vulnerabilities before they're
exploited. Both now share one umbrella: supply-chain findings flow into the same
`repair_suggestions` queue and the same Council, so the admin Sentinel overview
counts and reviews them too.

### Endpoints (admin-only)

```
GET  /api/admin/supply-chain/latest          — current posture snapshot + findings
GET  /api/admin/supply-chain/history         — recent sweep summaries
POST /api/admin/supply-chain/scan            — trigger a sweep (background)
POST /api/admin/supply-chain/autofix         — Council-gated auto-apply (background, no human)
POST /api/admin/supply-chain/remediate       — plan only / suggest-only (auto_apply=false)
GET  /api/admin/supply-chain/remediations    — applied-fix audit log
```

**Coverage gaps (honest, on the roadmap):** deep SAST (`Semgrep`/`CodeQL`),
DAST against the live app (`ZAP`/`Nuclei`), PII discovery for Law 25
(`Presidio`), container/IaC scanning (`Trivy`/`Checkov`), and an automated
`yarn build` gate before frontend upgrades go live.


## Customer portal (`/my`)

The customer-facing portal is URL-routed and guarded (iter D-82c). `/my` is the
public-with-overlay Luxe home; the 8 sub-pages mount inside **`CustomerShell`**
behind **`CustomerGuard`** (valid customer token → render, else bounce to `/my`
login overlay):

```
/my            Luxe dashboard home (public + auth overlay)
/my/website    site score, vulnerabilities, "Initiate AUREM Repair", scan schedule
/my/reviews    Google reviews          /my/social     social status
/my/report     monthly report          /my/referrals  referral link + rewards
/my/billing    Stripe + Apple Pay      /my/ora        ORA chat (business context)
/my/settings   API key + install snippet
```

Six wiring gaps behind these pages were closed in `missing_endpoints_router.py`
(iter D-83): `GET /api/admin/evolver/status`, `GET /api/admin/system-pulse-live`,
`GET+POST /api/customer/scan-schedule`, `GET /api/sentinel/fixes-log`,
`GET /api/sentinel/pulse-history`, `GET /api/site-monitor/me/sites` — every one
reads a real collection (zero mocks).

## Wiring verifier (CI)

`scripts/wiring_check.py` diffs every frontend `/api/…` call against the backend
route table (`--live <url>` reads `/openapi.json`; `--orphans` lists unimported
components). `tests/test_lean_prune_drift.py` fails the build if any live frontend
call matches a production-pruned prefix — so the lean-prune list can never
silently 404 a working feature. The admin **`/admin/wiring-audit`** page verifies
the full 9-group sidebar surface row-by-row at runtime.

---

---



## Zero-downtime deploys

Five guards make rolling K8s deploys safe (iter D-63):

1. **Smart readiness probe.** `/api/ready` does a cached Mongo ping (1 s timeout, 5 s TTL). K8s holds traffic off a pod until Mongo is reachable.
2. **Graceful APScheduler shutdown.** Scheduler exposed on `app.state.scheduler`; on SIGTERM, `shutdown(wait=True)` drains in-flight jobs before Mongo closes. Prevents duplicate auto-blasts on rolling restart.
3. **MIGRATION_RULES doc.** Codified 3-deploy rule (Additive → Dual-Read → Cleanup) for any schema change. PR checklist enforces it.
4. **SSE reconnect wrapper.** `useReliableSSE` hook with exponential backoff (1 s → 30 s + jitter), reconnects on tab refocus and network recovery.
5. **Feature flag system.** `services/feature_flags.py` with deterministic per-tenant SHA256 bucketing; flag changes never flicker users between on/off during rollouts.

Combined with health-probe middleware, AUREM achieves observed pod-swap windows under 1 second.

---

## Tech stack

**Backend**
- Python 3.11 · FastAPI · Uvicorn · Motor (async Mongo) · Pydantic v2
- APScheduler · httpx · radon · python-jose · passlib · python-dotenv

**Frontend**
- React 19 · React Router v7 · Tailwind CSS v3 · shadcn/ui · Lucide icons
- Motion (framer-motion) · sonner · @tanstack/react-query

**Infrastructure**
- MongoDB Atlas (production) · local MongoDB (preview)
- Emergent native deployment → Kubernetes
- Cloudflare CDN/edge · nginx ingress
- Supervisor (uvicorn + craco hot-reload)

---

## Third-party integrations

| Service | Purpose | Production status |
|---|---|---|
| OpenRouter (Emergent Universal Key) | LLM gateway (Claude Sonnet 4.5 / Gemini 3 / GPT-5.2) | 🟢 live |
| Apollo.io | B2B lead discovery + enrichment | 🟢 live |
| Stripe | Subscriptions + metered usage + Connect | 🟢 **LIVE keys** |
| Resend | Transactional + cold outbound email | 🟢 live |
| Tavily | Web search + URL content extraction | 🟢 live (cost ~$0.008/q) |
| Twilio | SMS (transactional + marketing) | 🟢 live |
| Retell AI | AI voice calls (closer-day-5, hot-lead) | 🟢 live (~$0.07/min) |
| WHAPI | WhatsApp Cloud channel | ⚪ disabled (account restriction April 2026) |
| Telegram | Founder alerts + ORA bell | 🟢 live |
| Shopify | OAuth + Pulse SEO scanner | 🟢 OAuth wired |
| GitHub | Code surface for CTO Skills + Deploy Gate | 🟢 live |

---

## Quick start (developers)

```bash
# Backend
cd /app/backend
pip install -r requirements.txt
sudo supervisorctl restart backend

# Frontend (always use yarn, not npm)
cd /app/frontend
yarn install
sudo supervisorctl restart frontend

# Run the full pytest suite
cd /app/backend
python -m pytest tests/ -q

# Run just the iter-by-iter regression suite (D-61 → D-70)
python -m pytest tests/test_d6*.py tests/test_d7*.py tests/test_health_chip_signal.py -q
```

**Hot reload:** Both backend and frontend auto-reload on file save. Only restart Supervisor after `.env` changes or new package installs.

**Logs:**
```bash
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/frontend.err.log
```

---

## Environment variables

Expected in `backend/.env` (all values omitted for security; never commit real values):

```
# Core
MONGO_URL=mongodb+srv://...
DB_NAME=aurem
JWT_SECRET=...
AUREM_ENCRYPTION_KEY=...
EMERGENCY_RESET_SECRET=...

# LLM gateway (Emergent Universal Key — covers Claude/Gemini/GPT/Sora/Whisper)
EMERGENT_LLM_KEY=...

# Outreach
APOLLO_API_KEY=...
TAVILY_API_KEY=...
RESEND_API_KEY=re_...
TELEGRAM_BOT_TOKEN=...

# Voice + messaging
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WA_FROM_NUMBER=               # optional, leave empty if using Retell only
RETELL_API_KEY=...
RETELL_FROM_NUMBER=+1...
RETELL_AGENT_ID=...
WHAPI_API_TOKEN=...                   # optional
WHAPI_BLAST_DISABLED=true             # set when WHAPI account is restricted

# Payments (LIVE keys in production)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Optional
PAGEINDEX_API_KEY=                    # leave empty to disable feature
```

Frontend reads only `REACT_APP_BACKEND_URL` from `frontend/.env`.

---

## Founder-facing features

| Feature | Route | Notes |
|---|---|---|
| Live system telemetry | `/admin/pillars-map` | 4 pillars, drill 3 levels deep |
| Codebase health | `/admin/codebase-health` | auto-refresh 30 s, scan every 6 h |
| Campaign health + autofix | `/admin/campaign-health` | 13 channel checks, 1-click fixes |
| ORA chat (admin) | `/admin/ora` | CTO + Console + Skills tabs |
| Web search (Tavily) | `/admin/web/search` or inline in ORA | auto-detect URL paste & search keywords |
| Auto-build websites | `/admin/awb-cockpit` | per-customer site generator |
| Stem-Fix queue | embedded in Pillars Map | approve/reject Claude refactors |
| Self-Repair Loop | embedded in Pillars Map | canary 10% deploy of safe fixes |
| Boardroom P&L | `/admin/boardroom` | trial → MRR → LTV breakdown |
| Feature flags | `/admin/feature-flags` | per-tenant rollout control |
| ORA Dev Console | `/admin/ora-dev` | proposal review with diff view |
| Memoir | `/admin/memoir` | Git-versioned semantic memory |
| Customer health | `/admin/customer-health` | per-tenant churn-risk score |
| Bug capture | floating widget (every page) | native BugCatch, no Sentry needed |
| Integrations | `/admin/integrations` | API key status, rotation |
| Skills Library | `/admin/skills-library` | 1.4 k LLM-invocable skills |
| Sentinel diagnostics | `/admin/sentinel` | deep system probe |
| Git Commit Gate | `/admin/git-gate` | approve every ORA-proposed commit |
| System Pulse Live | `/admin/system-pulse-live` | per-second endpoint sweep |

---

## Public API (commercialised)

Paying customers can call AUREM directly. All endpoints are metered through Stripe per call.

```
POST /api/v1/public/ora/chat              Chat with the ORA agent
GET  /api/v1/public/ora/skills            List available skills
POST /api/v1/public/web/search            Tavily web search (forthcoming)
GET  /api/v1/public/keys/usage            Your usage + cost so far
```

Auth: `Authorization: Bearer <your-api-key>` (issue keys at `/admin/api-keys`).

Docs: `memory/PUBLIC_API_USAGE.md`.

---

## Test coverage

418 pytest files. Every code-level fix from iter D-61 through D-70 is guarded by a regression test:

| Iter | What it locks in | Tests |
|---|---|---:|
| D-61 | mock purges (shopify scaffold, pageindex, label fixes) | 9 |
| D-62 | ORA Dev orphan-proposal filter + cleanup | 4 |
| D-63 | zero-downtime probe + scheduler graceful shutdown + flags + SSE | 13 |
| D-64 | Tavily web search skills + URL fetch + internal-URL blocklist | 17 |
| D-65 | scheduler coroutine-wrap fix (8 silent failures resolved) | 7 |
| D-66 | campaign health real fixes (4 yellows → green) | 10 |
| D-67 | Retell voice channel + engagement summary | 7 |
| D-68 | sidebar dedupe round 1 | 10 |
| D-69 | sidebar dedupe round 2 | 5 |
| D-70 | live codebase health analyzer | 10 |
| Misc | health chip signal | 3 |
| D-82 | autonomous supply-chain scanner (bandit + detect-secrets + pip-audit + yarn-audit) | 4 |
| D-82b | Council-gated remediation planner + version-safety + lanes | 4 |
| D-82c | lean-prune drift guard (CI — frontend ref ∉ pruned prefix) | 1 |
| | **Combined** | **104/104 PASS** |

---

## Known debt

The Codebase Health analyzer (§7) is brutally honest. Current snapshot scores **0.0 / 10**. Here is what's outstanding, sorted by priority:

### 🔴 P0 — God-files (refactor candidates)

| File | Lines | Concern |
|---|---:|---|
| `routers/registry.py` | 4,340 | imports 231 modules, CC=483 on `register_all_routers` |
| `services/ora_tools.py` | 4,242 | needs split by tool category |
| `services/ora_agent.py` | 3,932 | merge with `ora_council.py` discussion |
| `routers/aurem_chat.py` | ~3,500 | CC=260 on `_aurem_chat_inner` |
| `server.py` | 2,849 | lifespan + middleware + lifecycle all in one |
| `routers/pillars_map_router.py` | 2,300 | telemetry generator |
| `routers/cto_projects.py` | 1,952 | discovered manually pre-D-70 |

Total: **13 backend files ≥ 1,500 lines.**

### 🟠 P1 — Circular imports (5 detected)

Listed in the live `/admin/codebase-health` page → "Circular Imports" panel. Each one is a refactor that introduces a third module to break the cycle.

### 🟡 P1 — High complexity hotspots

| Function | CC | Why it matters |
|---|---:|---|
| `register_all_routers` | 483 | every router boots through it; new integrations slow boot |
| `_aurem_chat_inner` | 260 | ORA chat reasoning loop |
| `stream_scan` | 152 | live SSE scanner |
| Others (CC ≥ 30) | varies | see Codebase Health dashboard |

### ⚪ P2 — Operational debt

- **Resend webhook URL not configured** in dashboard → `template_perf` engagement signals partial.
- **WHAPI account restriction (April 2026)** → WhatsApp via Twilio fallback only; Meta WhatsApp Cloud API migration planned.
- **Hetzner Cloud API token not provided** → CTO Agent can propose deploys but can't SSH-execute on customer servers yet.
- **K8s readinessProbe path** still points to `/api/health` instead of D-63's smarter `/api/ready` (needs Emergent Support 1-line change).
- **6 SSE consumers** still use raw `EventSource` instead of D-63's `useReliableSSE` reconnect hook (progressive migration).

### 🔴 P0 — Enterprise readiness gaps

These are production debt that an enterprise audit will flag. Not optional for B2B sales.

- **APScheduler is in-process, not Redis-backed.** `legion/docker-compose.yml` already runs Redis, but `routers/registry.py` uses `AsyncIOScheduler` with a Mongo jobstore. **Risk:** when AUREM runs 2+ pods, every scheduled job will fire on every pod → duplicate auto-blasts, double Stripe charges, repeated voice calls. **Fix:** migrate to `RedisJobStore` + Redis-backed lock. ~2 hrs.
- **Row-Level Security is app-layer only.** Every router manually applies `{"tenant_id": tenant}` filters. **Risk:** one missed filter in a future PR → cross-tenant data leak. SOC 2 auditors will fail this. **Fix:** Mongo Atlas database-level access rules + a tenant-scope middleware that injects the filter automatically. ~4 hrs.
- **74 of 77 SuperSkills are dormant.** `skills_manager.py` registers only 3 (`tdd-workflow`, `security-review`, `connector-pattern`) out of 77 JSON manifests. **Risk:** dead weight inflates the surface area without delivering value; founders/customers think they have powers they don't. **Fix:** either wire the remaining 74 or delete the JSON files. ~3 hrs to audit + decide.
- **MCP server marked `# SLEEPING`.** Wired in code but never activated in production. **Risk:** if anyone calls the MCP endpoint expecting model-context-protocol behavior, they get silence or a 500. **Fix:** either activate (with proper auth + rate limit) or remove the route. ~1 hr.

### How to track

The Codebase Health dashboard at `/admin/codebase-health` is the single source of truth. It auto-refreshes every 30 s on the page and the analyzer re-runs every 6 h. The "Top Action" banner names the next file to fix, with a one-line reason.

When you split or simplify a file, the score climbs the next snapshot. No manual updates to this README needed.

### Active refactor — D-71 (queued)

The Codebase Health dashboard has already named the next file to fix: `routers/registry.py`. The strangler-fig plan is documented and approved; execution begins in the next coding session.

**Target shape:**
```
backend/routers/registry.py            ← stays, becomes a ~50-line orchestrator
backend/routers/_register/
    __init__.py                        ← exposes register_all_routers()
    _schedulers.py     (~400 lines)    ← STEP 1: all APScheduler add_job calls
    _admin.py          (~400 lines)    ← STEP 2: /admin/* routers
    _ora.py            (~250 lines)    ← STEP 2: /api/ora/* + skills
    _sales.py          (~350 lines)    ← STEP 3: P1 — Apollo, Scout, Closer, Blast
    _billing.py        (~200 lines)    ← STEP 3: P2 — Stripe, Trial, Compliance
    _monitor.py        (~200 lines)    ← STEP 3: P3 — Sentinel, Site Monitor
    _core.py           (~150 lines)    ← STEP 4: health, auth, base
    _customer.py       (~200 lines)    ← STEP 4: /customer/* + onboarding
    _commercial.py     (~150 lines)    ← STEP 4: /v1/public, API keys
```

**Expected outcome:** `register_all_routers` CC drops from **483 → ~25** per sub-function. No file > 500 lines. Health score climbs **0.0 → 6-7** in one snapshot.

**Execution:** 4 steps × ~30 min each. Full pytest + Pillar Map heartbeat verification after every step. Founder approves each step before the next. Safety net: 95 regression tests + 6 h Codebase Health auto-rescan provide instant feedback per step.

---

## Conventions & rules

- **Routing:** every backend route MUST be prefixed `/api`. URLs come from environment variables only — no hardcoded ports or hosts.
- **MongoDB:** always exclude `_id` from responses (`projection={"_id": 0}`). Use `datetime.now(timezone.utc)`, never `utcnow()`.
- **No mocks, ever.** If an integration is missing, raise HTTP 503 with the env-var name in the detail. Founder must know what's wrong.
- **No background work outside APScheduler.** All cron jobs go through `routers/registry.py`'s scheduler block. Pass coroutine functions + `args=[...]`, never `lambda: foo(...)` (D-65 lesson).
- **Migrations follow the 3-deploy rule** (Additive → Dual-Read → Cleanup). See `memory/MIGRATION_RULES.md`.
- **Test IDs:** every interactive element gets a `data-testid` in kebab-case.
- **Sidebar dedupe rule (D-68/69):** if a feature already lives as a tab/panel inside another page, do not give it a second sidebar entry. Route stays mounted for bookmarks.

---

## License

Proprietary. Founder contact: **teji.ss1986@gmail.com**.
Commercial use requires written permission.

---

*Last updated: 2026-06-12 · iter D-83 · 104/104 tests pass*
