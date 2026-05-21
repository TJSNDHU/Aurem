# AUREM — Autonomous Orchestration Platform (PRD)

## Vision
Full-sovereignty, token-conscious autonomous business operator. Local MongoDB + local Legion LLM via reverse-poll daemon. Cloud LLMs (Claude via Emergent, DeepSeek via OpenRouter) used surgically.

## Environments
- **Preview**: dev pod — auto-deploy on save.
- **Production**: `aurem.live` — Founder pushes manually from Preview.

## Core Pillars
1. **Auto-Blast Engine** — Outbound sales orchestration.
2. **LLM Gateway v2** — DeepSeek V3.1 (logic/repair) + Claude (sensitive: auth/billing).
3. **Autonomous Repair Stack** — Scanners → Incident Bus → Triage Brain → ORA CTO → Auto-apply (Tier 1) / Telegram approval (Tier 2).
4. **Nightly Self-Check** — 13 pillars probed twice daily, autoheal + email report.
5. **Customer Dashboard V2** — Apple-style edge-to-edge UI, auto dark/light, responsive 3 breakpoints.

## Recently Completed
- iter 325g: React Doctor + lazy loading + CI + ReRoots→AUREM rebrand.
- iter 325h: Async bcrypt login fix + Free SEO Audit funnel + Retell signature fix.
- iter 325i: Deep Retell nightly probe (catches signature drift + failure rate).
- iter 325j: DeepSeek V3.1 wired into ORA chat (replaces dead Ollama default).
- iter 325k: Redis pool cap lowered 12→10 for free-tier headroom.
- iter 325l: resend + RerootsBrowser startup-import warnings eliminated.
- iter 325m: Idempotent brand-purge migration (ReRoots strings → AUREM in Mongo on every boot).
- iter 325n: **Customer Dashboard V2** — pixel-perfect Apple-style redesign with 11 components, 3 responsive breakpoints, auto dark/light mode, 18 contract tests passing, live-data wired via existing hook.
- iter 325s: Online/offline blink fix — useAuthFetch retry + useLiveApi 3-strike debounce.
- iter 325t: requirements.txt slim (-3.4 GB ML/GPU bloat) + APScheduler ThreadPool 30 workers + 90s misfire grace.
- iter 325u (current): **APScheduler overload + watchdog noise fix** —
  • `warm_probe_tick` now fans out endpoints in parallel via `asyncio.gather` (was serial; 50s worst-case → ~5s).
  • Warm-prober scheduler: `max_instances=2`, `misfire_grace_time=120` — absorbs single overlap, stops "max instances reached" warnings.
  • `ora_campaign_watchdog` only emits to `incident_bus` on the *trip transition* and every 30x escalation (was every 60 s → 232 dup incidents in 4 hours).
  • Stdout `[watchdog] tripped guards` print follows same dedup cadence.
  • **Topbar degraded-state pulse** — yellow when API streak ≥ 2, red when ≥ 3. Renders BEFORE the user sees a full red error UI.
  • 5 regression tests in `tests/test_iter325u_overload_fixes.py` all green.
- iter 326g (2026-02): **ORA chain — FreeLLMAPI skipped, Gemini + NVIDIA baked in** —
  • Default chain now `deepseek → gemini → nvidia → claude → groq` (FreeLLMAPI + Legion Ollama removed from default).
  • Fixed `NameError` shield: `_GEMINI_HTTPX_TIMEOUT/WAIT_FOR` + `_NVIDIA_HTTPX_TIMEOUT/WAIT_FOR` were USED but never DECLARED — providers would have crashed on first call.
  • `gemini_health()` now surfaces Google's structured error message (e.g. "Consumer ... has been suspended") instead of opaque "HTTP 403".
  • Live-verified end-to-end: NVIDIA healthy (123 models, 124 ms latency); Gemini returns 403 because the current `GOOGLE_API_KEY` is suspended by Google — chain gracefully fell through to NVIDIA which served the reply via `meta/llama-4-maverick-17b-128e-instruct`.
  • 9 regression tests in `tests/test_iter326g_chain_gemini_nvidia_bake.py` all green.
  • **Action for founder**: rotate `GOOGLE_API_KEY` in `/app/backend/.env` (current one suspended) to unlock the fastest fallback in the chain. NVIDIA + Claude + Groq + DeepSeek already keep ORA fully operational.
- iter 326h (2026-02): **3 critical DB bug fixes in one PR** —
  • **FIX 1**: `services/founder_provision.py` now mirrors the founder into `admin_users.passwordHash` (camelCase, matching the RBAC `/auth/rbac/login` contract). Backfills from `users.password_hash` when no env seed is configured so existing prod accounts get healed automatically. Founder `teji.ss1986@gmail.com` can now log in via RBAC.
  • **FIX 2**: `services/auto_blast_engine.py::_reset_zero_streak_on_success` — auto-resets `ora_campaign_health.zero_sent_streak = 0` and pulls `zero_sent_streak` out of `tripped` whenever a cycle delivers ≥1 send. Idempotent no-op when sent=0. Live verified: streak 205 → 0 after manual run.
  • **FIX 3**: `services/ensure_audit_log_ttl.py` — drops broken `ts_ttl_35d` (wrong field) and installs `ttl_timestamp_7d` (604800s) on the correct `timestamp` field of `api_audit_log`. Wired into server startup. Live TTL monitor already purged ~590k stale rows (1.4M → 803k; oldest now exactly 7 days old).
  • 10 regression tests in `tests/test_iter326h_3_critical_db_fixes.py` all green.

## Backlog (Priority Order)
- **P1**: ORA Status frontend view — single-screen 9-metric dashboard + Approve queue badge.
- **P2**: AWB (Website Builder) quality eval — render 5 sample sites.
- **P2**: Apply same deep-probe pattern to Stripe + Twilio (webhook secret drift, from-number ownership drift).
- **Blocked**: Google Places + Yelp keys (awaiting user billing rotation).

## Test Credentials
See `/app/memory/test_credentials.md`.

## Key Files
- `backend/services/aurem_nightly_selfcheck.py` — 13-pillar probe + autoheal.
- `backend/services/ora_cto_repair_agent.py` — DeepSeek-driven code fixer.
- `backend/services/agents/closer_ora.py` — outbound voice orchestrator.
- `backend/routers/voice_agent_router.py` — Retell call API wrapper.
- `backend/routers/nightly_selfcheck_router.py` — `/api/admin/selfcheck/*`.
- `backend/services/brand_purge_migration.py` — startup ReRoots→AUREM string sweep.
- `frontend/src/platform/luxe/LuxeDashboardV2.jsx` — Apple-style customer dashboard.
- `frontend/src/platform/luxe/components/*.jsx` — 9 modular dashboard cards.
- `frontend/src/styles/dashboard-theme.css` — Theme tokens, 3 breakpoints.
- `frontend/src/platform/luxe/useTheme.js` — auto-detect dark/light + localStorage.
