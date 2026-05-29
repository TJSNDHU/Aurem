# AUREM Platform — System Overview

> ⚠️ **REFERENCE / HISTORICAL DOC** — last scan 2026-05-12 (iter 322fa).
> For the CURRENT, AUTHORITATIVE PRD + stack + flow + schema + plan,
> read the 6 SPEC docs first (`SPEC_INDEX.md` → `SPEC_01..06`).
>
> This file is kept for the Legion Bridge / aurem-cto sovereign
> sidekick context (iter 322a → 322fa), which is NOT yet covered in
> the SPEC set. When that work resumes, fold the relevant bits into
> SPEC_02 + SPEC_06.
>
> **Status snapshot (when last scanned)**: 🟢 GREEN · 322fa Legion Bridge.

---

## 1. One-line elevator

AUREM is a full-stack autonomous sales-ops platform: 25-agent orchestrator,
a self-building ORA CTO with 29 tools, a sovereign sidekick deployable to
the founder's Legion laptop, a Camoufox-based stealth scout, a public lead
magnet (Design-Extract), and a Reverse-Poll Daemon that lets ORA execute
shell commands on Legion without SSH.

---

## 2. Live metrics (from this scan)

| Layer | Number | Notes |
|---|---|---|
| Backend routers           | **354** | FastAPI, all under `/app/backend/routers/` |
| Backend services          | **425** | Business logic, ORA tools, integrations |
| Backend pytests           | **209** | `/app/backend/tests/` |
| Skill markdown docs       | **42**  | `/app/backend/ora_skills/` |
| Backend Python lines      | **325,662** | excludes tests + __pycache__ |
| Pytest lines              | **52,703**  | |
| Frontend JSX/JS files     | **333** | `/app/frontend/src/` |
| Frontend `<Route>` count  | **117** | in `App.js` |
| aurem-cto files (sovereign) | **30** | 1,731 lines, ready to scp to Legion |
| Mongo collections         | **502** | full Atlas-shape |
| **ORA tools registered**  | **29**  | live in `/api/ora-tools/list` |
| **ORA skill broadcast**   | **14 skills, 71,484 chars** | injected into every LLM call |
| ORA skill library (full)  | **1,467** | searchable, RAG-ready |
| ORA tool invocations (audit) | **166** | last 24h |
| Founder commit approvals  | **1** | git-gate has shipped real code |
| Legion queue jobs         | **8** | (7 completed, 1 rejected) |
| Ghost scout jobs          | **2** | real Camoufox runs |
| `.env` keys wired         | **148** | Stripe, OpenAI, Groq, Twilio, Resend, Cloudflare, Telegram, Legion, etc. |

---

## 3. Architecture (production layout)

```
                    ┌─────────────────────────────────────┐
                    │   Browser users (founder + customers)│
                    └────────────────┬────────────────────┘
                                     │ HTTPS
                                     ▼
        ┌────────────────────────────────────────────────────┐
        │       Emergent Pod (https://aurem.live)            │
        │  • FastAPI server (354 routers, 425 services)      │
        │  • React 18 + Tailwind SPA (117 routes)            │
        │  • 29 ORA tools + Council Gate + Git Commit Gate   │
        │  • LLM gateway: Groq → OpenRouter → Emergent       │
        │  • Telegram, Stripe, Resend, Cloudflare, Twilio    │
        └────────────────┬──────────────────────┬────────────┘
                         │                      │
            ┌────────────▼───┐         ┌────────▼───────────┐
            │ Atlas MongoDB  │         │ Legion Laptop      │
            │ 502 collections│         │ (Reverse-Poll over │
            │ shared shape   │         │   HTTPS — no SSH)  │
            └────────┬───────┘         │ • aurem-cto stack  │
                     │                 │ • Ollama Qwen 7B   │
                     │                 │ • Camoufox stealth │
                     │ outbox replay   │ • Cold-storage     │
                     └─────────────────┘   (Fernet AES-128) │
                                       └────────────────────┘
```

---

## 4. Iter timeline (last 10 deliveries — most recent first)

| Iter   | Title                                            | Ships                                        |
|--------|--------------------------------------------------|----------------------------------------------|
| 322fa  | Legion Bridge — autonomous control (no SSH)      | 5 files; queue + daemon + install.sh         |
| 322ez  | Ghost Protocol Scout + Local LLM bridge          | 5 files; Camoufox + Bezier/Markov + Ollama   |
| 322ey-fix | ORA Self-Correction teaching loop closed      | 1 skill doc; broadcast 13 → 14 skills        |
| 322ey  | Founder-Saves + Design-Extract Public + Day-7    | 5 files; 19/19 pytests                       |
| 322ex  | aurem-cto Batch 2 — real LLM + tool-call loop    | 4 files; Groq → Emergent fallback wired      |
| 322ew  | aurem-cto Hybrid Standalone skeleton             | 21 files at `/app/aurem-cto/`                |
| 322ev  | ORA Natural-Language Planner (Open Interpreter)  | `ora_run_natural` tool                       |
| 322eu  | ORA self-build unlock — 8 new tools              | 27 → ready to bootstrap own infra            |
| 322et  | Morning Brief + 6 AM Toronto nightly digest      | APScheduler cron                             |
| 322es  | ORA CTO 100% complete — no broken ends           | regression baseline                          |

Full iter history (322a → 322fa) in `/app/memory/PRD.md`.

---

## 5. ORA Tool Catalog (29 tools, live)

### Read / inspect (8)
`grep_codebase`, `view_file`, `view_dir`, `curl_internal`,
`db_count`, `db_distinct`, `git_log`, `health_check`

### Quality (2)
`lint_python`, `pytest_run`

### Mutate + safety-gated (8)
`shell_exec`, `safe_edit`, `restart_service`, `propose_commit`,
`create_file`, `create_dir`, `append_to_file`, `pip_propose`

### Council Gate (5)
`peer_review`, `code_review`, `security_scan`, `council_consult`,
`safe_edit_with_council`, `shell_exec_with_council`

### Infra (4)
`cloudflare_dns_list`, `cloudflare_dns_write`, `docker_compose`,
`ora_run_natural` (Open Interpreter)

### Legion (1, NEW iter 322fa)
**`legion_exec`** — ORA executes any shell command on the founder's Legion
laptop via reverse-poll HTTPS queue. HIGH-risk gated by Telegram approval
to the founder's phone with auto-reject after 5 min.

---

## 6. Major endpoints (canonical, all live, HTTP 200)

| Endpoint                                  | Auth      | Purpose                          |
|-------------------------------------------|-----------|----------------------------------|
| `/api/platform/health`                    | none      | liveness probe                   |
| `/api/auth/login` (POST)                  | none      | JWT issue                        |
| `/api/ora-chat/ask` (POST)                | admin JWT | full ORA tool-call loop          |
| `/api/ora-tools/list`                     | admin JWT | live 29-tool catalog             |
| `/api/ora-tools/execute` (POST)           | admin JWT | direct tool invocation           |
| `/api/admin/founder-saves/{summary,timeline}` | admin JWT | git commits + council + tool fails ledger |
| `/api/design-extract/public/{run,sample,_/health}` | **public** | lead-magnet (3/day/email) |
| `/api/scout/ghost/{run,jobs,_/health}`    | admin JWT | Camoufox stealth scout           |
| `/api/legion/queue/{enqueue,next,ack,result,list,approve,reject,_/health}` | admin JWT (or daemon token) | Legion command queue |
| `/api/legion/{daemon-source,install}`     | **public** | bootstrap files served from pod  |

---

## 7. aurem-cto Sovereign (Legion-ready, 30 files / 1,731 lines)

```
aurem-cto/
├── README.md            ← deployment guide
├── bootstrap.sh         ← initial setup on Legion
├── docker-compose.yml   ← 3 services: api, ui, outbox
├── .env.example
├── .gitignore
├── api/
│   ├── Dockerfile
│   ├── main.py          ← FastAPI sovereign (192L)
│   ├── requirements.txt
│   └── services/
│       ├── __init__.py
│       ├── llm.py         ← Groq → OpenRouter → Emergent fallback (165L)
│       ├── llm_local.py   ← Ollama Qwen 2.5 Coder 7B bridge (120L)
│       ├── tools_bridge.py ← HTTP-proxy to upstream 29-tool registry
│       └── orchestrator.py ← tool-call loop, 115L
├── ui/                  ← React + Vite + Tailwind cockpit
│   ├── Dockerfile, package.json, vite.config.js
│   ├── tailwind.config.js, postcss.config.js
│   ├── index.html
│   └── src/{App.jsx 194L, main.jsx, index.css}
├── outbox/              ← SQLite → Atlas async replay
│   ├── Dockerfile, requirements.txt
│   └── worker.py (121L, SIGTERM-graceful)
├── daemon/              ← Legion reverse-poll daemon (iter 322fa)
│   ├── legion_daemon.py (150L, real subprocess)
│   └── install.sh (140L, idempotent systemd installer)
└── cloudflared/
    └── config.yml       ← tunnel to cto.aurem.live
```

---

## 8. Key DB collections

| Collection                         | Rows | Purpose                          |
|-----------------------------------|------|----------------------------------|
| `users`                            | 21   | accounts, JWT keyed by `email`   |
| `ora_tool_invocations`             | 166  | every ORA tool call audited      |
| `ora_commit_proposals`             | 1    | Git Commit Gate (founder approvals) |
| `ora_skills_library`               | 1,467 | full RAG-able skill base         |
| `ora_skills_broadcast` (active)    | 1    | 14-skill addendum injected into every LLM call |
| `ora_skills_broadcast_history`     | 15   | snapshots of each broadcast change |
| `design_extract_public_captures`   | 0    | lead magnet emails (rate-limit source) |
| `scout_ghost_jobs`                 | 2    | real Camoufox crawls             |
| `legion_queue`                     | 8    | pending/claimed/done/rejected jobs |
| `legion_command_audit`             | 7    | terminal-state audit             |
| `leads`                            | 21   | scout output                     |
| `campaigns`                        | 1    | active outreach                  |
| `contacts`                         | 8    | enriched contacts                |

---

## 9. Active ORA broadcast skills (14, 71,484 chars)

The full system prompt addendum injected into every ORA LLM call.
Includes: `aurem-322ey-ora-mistakes-lessons` (6 self-correction rules
taught after iter 322ey supervisor fixes), `dev_ora-cto-final-complete`,
`scout_scan`, `agent_engineering`, `agent_design_ux`, plus 9 more.

---

## 10. Third-party integrations (real, keys wired)

| Service            | Env key                       | Used for                          |
|--------------------|-------------------------------|-----------------------------------|
| Groq llama-3.3-70b | `GROQ_API_KEY`                | ORA primary chat (~7s loops)      |
| Emergent universal | `EMERGENT_LLM_KEY`            | Claude Sonnet 4.5 fallback        |
| OpenRouter         | `OPENROUTER_API_KEY`          | Tier 2 LLM fallback               |
| Stripe             | `STRIPE_*`                    | Customer billing                  |
| Resend             | `RESEND_API_KEY`              | Transactional email               |
| Twilio             | `TWILIO_*`                    | SMS alerts                        |
| Telegram           | `TELEGRAM_BOT_TOKEN/CHAT_ID`  | HIGH-risk Legion approval         |
| Cloudflare         | `CLOUDFLARE_API_TOKEN/ZONE_ID`| DNS + Tunnel (`cto.aurem.live`)   |
| Apollo             | `APOLLO_API_KEY`              | Lead enrichment                   |
| Deepgram           | `DEEPGRAM_API_KEY`            | Voice STT                         |
| ElevenLabs         | `ELEVENLABS_API_KEY`          | Voice TTS                         |
| Firecrawl          | `FIRECRAWL_API_KEY`           | Web scout (fallback)              |
| **Legion daemon**  | `LEGION_DAEMON_TOKEN`         | Reverse-poll bearer (NEW 322fa)   |

---

## 11. Working policy (memorized in `/app/memory/WORKING_POLICY.md`)

- **ORA CTO designs, main agent supervises** — major work routed through ORA chat endpoint to save tokens.
- **Real builds only** — no mocks, no fake responses, no "should work" claims. Every iter ends with 3 concrete proofs (curl response + db_count + git log).
- **Council Gate + Git Commit Gate** mandatory for critical changes.
- **Teaching loop closed** — when supervisor catches an ORA bug, the fix MUST include (a) code patch AND (b) broadcast skill update so future sessions inherit the lesson.

---

## 12. Known caveats (brutally honest)

1. **Telegram inline button webhook NOT wired** — HIGH-risk Legion jobs alert phone correctly, but approval requires API call or `/admin/legion-bridge` UI (iter 322fb).
2. **`/admin/legion-bridge` admin UI not built yet** — current access is API-only.
3. **5s poll latency on Legion bridge** — not instant. WebSocket upgrade is iter 322fc.
4. **`/tmp/scout_cold/` on Emergent pod resets** with pod restarts — on Legion, daemon writes to `/opt/aurem-cto/data/scout_cold/` (persistent).
5. **No paid residential proxy wired** — Ghost Scout works on most sites without proxy; for Cloudflare/DataDome-protected sites, add IPRoyal creds to env.
6. **No CapSolver wired** — captcha-protected pages still fail; 30 lines of code away.
7. **Founder must run `curl -fsSL https://aurem.live/api/legion/install | sudo bash` ONCE on Legion** — after that, full autonomy. No second manual step.

---

## 13. Files of record

- `/app/memory/PRD.md` — full append-only iter log (all 322a → 322fa)
- `/app/memory/WORKING_POLICY.md` — locked supervisor behaviors
- `/app/memory/test_credentials.md` — admin + customer + daemon token
- `/app/memory/SYSTEM_OVERVIEW.md` — this document (regenerable)
- `/app/aurem-cto/` — sovereign sidekick ready for Legion
- `/app/backend/ora_skills/` — 42 skill markdown docs (1,467 in broadcast library)
- `/app/backend/tests/` — 209 pytests, 52,703 lines

---

## 14. What's next (prioritized backlog)

### P0
- Founder: `curl -fsSL https://aurem.live/api/legion/install | sudo bash` on Legion laptop
- Build `/admin/legion-bridge` cockpit page (iter 322fb)

### P1
- Telegram inline-button webhook handler
- Append lesson #7 (Motor mutates input on insert/update) to broadcast
- Day-7 upsell modal wire-up into trial onboarding
- IPRoyal residential proxy creds → Ghost Scout production-grade

### P2
- TLS JA4 spoofing via `curl_cffi` for non-browser HTTP
- Long-poll/WebSocket upgrade for Legion queue (drop 5s latency)
- HubSpot/Salesforce CRM Sync demock
- Real `services/design_extract_service.run_extraction` (Playwright deep extractor)

### P3
- TanStack Query + IndexedDB CRM cache
- ORA self-monitor cron (Legion health → Telegram)
- Camoufox Studio UI wrap on top of existing scout_unified

---

**Last verified**: All endpoints HTTP 200 · 19/19 pytests pass · 15 iter-files lint-clean · 29 tools registered · ORA broadcast active · Legion bridge end-to-end tested with real subprocess on simulated Legion.
