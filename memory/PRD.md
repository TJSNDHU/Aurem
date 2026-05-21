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
- iter 325n (current): **Customer Dashboard V2** — pixel-perfect Apple-style redesign with 11 components, 3 responsive breakpoints, auto dark/light mode, 18 contract tests passing, live-data wired via existing hook.

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
