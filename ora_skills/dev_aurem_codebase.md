# AUREM Codebase Context

## Trigger intent
Any dev task on AUREM — **always** injected alongside other `dev_*` skills.

## Stack
- **Backend**: FastAPI + Python 3.11 (async / Motor)
- **Database**: MongoDB — access via `motor.motor_asyncio`, auto tenant-scoped
  through `services/scoped_db.py::TenantScopedDatabase`
- **Frontend**: React 18 + Tailwind + Shadcn UI
- **Deploy**: Emergent platform — supervisor-managed, hot-reload on
- **LLM Provider Chain** (iter 282al-5 — Sovereign first):
  1. **Legion Sovereign Node** (Lenovo Legion i9, Ollama, FREE).
     URL: `SOVEREIGN_NODE_URL` / `OLLAMA_URL` env. Default model:
     `SOVEREIGN_MODEL=llama3.1`. Update the URL whenever the
     ngrok / Cloudflare tunnel restarts.
  2. **OpenRouter cloud** (`OPENROUTER_API_KEY`) — pay-per-token fallback.
  3. **Emergent universal key** (`EMERGENT_LLM_KEY`) — last resort;
     may be budget-exhausted.
  Single entry point: `services/llm_gateway.py::call_llm(system, user)`.
  Never raises. Returns `"(LLM unavailable — all providers exhausted.)"`
  when every tier misses.
- **SMS**: Twilio A2P 10DLC (`+14314500004`) — shortlinks required
  (`aurem.live/r/<slug>`) to bypass carrier filter error 30007
- **Email**: Resend (`ora@aurem.live`), wrapped via `services/casl_compliance.py`
- **Payments**: Stripe (live mode)
- **Scout scan**: `services/website_scraper.py::scan_website()` —
  webclaw-aware, falls back to legacy httpx when `WEBCLAW_API_KEY` unset

## Key files
- `backend/aurem_config.py`         → SSOT for all runtime config
- `backend/server.py`               → uvicorn app + MongoDB client + middleware stack
- `backend/routers/registry.py`     → all schedulers, TTL index init, router includes
- `backend/services/skill_router.py`→ ORA skill routing (intent → skill → agent)
- `backend/services/outreach_composer.py` → LLM-composed drip messages (24h cache)
- `backend/services/shortlink_service.py` → `aurem.live/r/<slug>` mint + resolve
- `backend/shared/agents/`          → A2A agents (Scout, Envoy, Closer, Follow-up)
- `backend/routers/aurem_chat.py`   → `/api/aurem/chat` entry point, Truth-Sync
- `backend/routers/shortlink_router.py` → `/api/shortlinks/*`, `/r/{slug}`,
                                          `/api/admin/brief/health`
- `ora_skills/*.md`                 → ORA skill files (this dir)
- `agent_skills/*.md`               → Emergent build-agent reference skills

## Rules for ORA when coding
1. **Always read existing file before editing** — never rebuild what already exists.
2. **Every new collection needs a TTL** — add `expireAfterSeconds` in
   `registry.py::_shortlink_and_ttls` or its sibling init block.
3. **All new services: never raise** — catch + log via
   `logger.debug / logger.warning`. Public functions return typed shells.
4. **All new endpoints: prefix `/api`** and add a row to the Pillars Map
   chip if they affect a public user-facing surface.
5. **Run `ruff` after every file change**: `mcp_lint_python`.
6. **Run pytest after every backend change**: at minimum the tests for
   the changed module.
7. **MongoDB queries**: always exclude `_id` via projection
   (`projection={"_id": 0, ...}`). Mongo strips `tzinfo` on read —
   reattach `timezone.utc` before comparing datetimes.
8. **Env vars**: read via `os.environ.get(...)`, never hard-code.
   Frontend uses `process.env.REACT_APP_BACKEND_URL`.
9. **Do not touch `.env` protected keys**: `MONGO_URL`, `DB_NAME`,
   `REACT_APP_BACKEND_URL`.
10. **A2A skill files** (sales): edit `ora_skills/{scout,envoy,closer,
    followup}_*.md`. **Dev skill files**: edit `ora_skills/dev_*.md`.
    Never cross-contaminate.
