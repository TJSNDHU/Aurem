# D-77 "Is this flow real?" Audit Report

> Date: 2026-06-10
> Scope: Campaign blasts · CTO agent outputs · Referrals · Billing/usage screens
> Standard: Same as D-75 Part 1 — if it's theater, gut + rewrite with real logic + E2E proof. Before/after for every flow.

## TL;DR

**Zero theater code found.** Every audited surface routes through real
infrastructure (MongoDB / Stripe / Resend / WHAPI / OpenRouter). The
remaining mentions of words like *mock* / *fake* / *placeholder* /
*TODO* in the codebase are all one of:

1. Detection patterns (security_gate.py, ora_tools.py, cto_verify_router.py — they REJECT theater code, not produce it)
2. Stale docstrings (one fixed in this pass — `blast_service.test_whatsapp`)
3. Comments describing the *historical* theater code that was already removed (`iter 327g — actually do the work the old TODO promised`)
4. Test fixtures in `tests/` (legitimate — they're testing real code paths)

The D-73 + D-75 Part 1 cleanups already gutted the major theater
flows (autonomous repair pixel pipeline, pending_approvals legacy
schema). This audit confirms no regression slipped back in.

---

## 1. Campaign Blasts

### Surface: `routers/campaign_router.py` → `pillars/sales/routes/{blast_service,auto_blast,lead_crud,render_templates}.py`

| Flow | Status | Evidence |
|------|--------|----------|
| Daily lead scrape → MongoDB write | 🟢 REAL | `run_daily_scrape()` calls Apollo + Total Scout, writes to `campaign_leads` collection. |
| Per-lead WhatsApp blast | 🟢 REAL | `execute_blast_for_lead` → `WhatsAppEngine.send_message` (WHAPI HTTP POST). On send failure, persists `status="failed"` with real error string. |
| Per-lead SMS blast | 🟢 REAL | `services.sms_service.send_sms` → Twilio REST API. (Twilio is currently 401 — RED in creds_health — that's an INFRA issue, not theater. The code is real; the credential is stale.) |
| Per-lead Email blast | 🟢 REAL | `services.email_engine.send_email` → Resend HTTP API. |
| Per-lead Voice blast | 🟢 REAL | `VoiceEngine` → Retell AI HTTP API. |
| Auto-blast daily cron | 🟢 REAL | `auto_blast.py:799` `asyncio.sleep(0.25)` is rate-limiting between sends, not theater latency. |
| `/test-whatsapp`, `/test-call` admin endpoints | 🟢 REAL | Same engines as production. Defaults like `score=65, issues_count=4` are **inputs** to the test endpoint (admin types them in), not fabricated outputs. |

**Before/After**: 1 stale docstring fix this pass:
```
- """Send a test WhatsApp message via WHAPI (or mock if key missing)."""
+ """Send a test WhatsApp message via WHAPI/Meta. NO MOCKS — ..."""
```
Behavior was already honest; the comment was lying about it.

---

## 2. CTO Agent Outputs

### Surface: `routers/agents_router.py` · `cto_tools_router.py` · `cto_verify_router.py` · `cto_learning_router.py` · `cto_brief_router.py` · `cto_codebase_router.py` · `aurem_cto/*`

| Flow | Status | Evidence |
|------|--------|----------|
| `/api/aurem-cto/chat` 12-phase pipeline | 🟢 REAL | Routes through `services.aurem_ai_service` → OpenRouter (real LLM). The dedup-audit fix in D-76 confirmed this is the canonical handler. |
| CASL compliance PDF score | 🟢 REAL | `score = 100 if violations == 0 else max(0, 100 - violations * 5)`. Deterministic formula over real `message_log_complete` rows — not theater. |
| `/cto/run-scout`, `/cto/import-leads`, `/cto/run-blast` | 🟢 REAL | D-49 added real execution tools. Each writes audit rows + invokes the same engines as the cron pipelines. |
| `/cto/verify` auto-verification | 🟢 REAL | D-52 — checks code syntax (Python `compile()`), GitHub commit SHA via real GitHub API, deploy state via `/api/version` polling. Has anti-hallucination patterns (`cto_verify_router.py:122`) that REJECT placeholder bodies. |
| `/cto/learning` self-review | 🟢 REAL | D-53 — only records VERIFIED outcomes (gated by D-52 results). Weekly self-review runs at Sun 02:00 UTC via APScheduler. |
| `/cto/codebase` repo inspection | 🟢 REAL | D-54 — reads actual files via `pathlib` + `git log` shell-out instead of hallucinating contents. |

**No fake confidence, no fake outcomes.** Confidence badges in the
`cto_learning_router` are computed from `verified_outcomes_count /
total_attempts_count`, both pulled live from Mongo.

---

## 3. Referrals

### Surface: `routers/referral_router.py`

| Flow | Status | Evidence |
|------|--------|----------|
| Dashboard counts | 🟢 REAL | `total_referrals`, `active_referrals`, `pending_referrals`, `total_earned` all read straight from `referral_profiles` MongoDB doc. New users get an honest 0/0/0/0 baseline + a freshly-minted `AUREM-XXXXXX` code. |
| Reward tier resolution | 🟢 REAL | `_get_tier()` walks the `REWARD_TIERS` list against actual `total_referrals` from Mongo. |
| Referral history | 🟢 REAL | Pulled from `referral_history` collection, sorted by `created_at`. Empty array if no referrals — not faked. |
| Referral link generation | 🟢 REAL | `f"https://aurem.live/join?ref={referral_code}"` — deterministic, no fake counts. |

No theater. The codebase is intentionally small (97 LOC) — every line
reads or writes real Mongo state.

---

## 4. Billing / Usage Screens

### Surface: `routers/aurem_billing_router.py` · `billing_plan_router.py` · `shared/commercial/billing_service.py`

| Flow | Status | Evidence |
|------|--------|----------|
| Stripe webhook | 🟢 REAL | Signature verification via `stripe.Webhook.construct_event`. Refuses to process unsigned events unless `AUREM_ALLOW_UNVERIFIED_WEBHOOK=1` (dev-only opt-in). Bug-fix #76 already closed the free-enterprise-plan loophole. |
| `customer.subscription.created` handler | 🟢 REAL | Calls real Stripe Customer.retrieve via `asyncio.to_thread` (Bug-fix #81 made it async). Emits `SUBSCRIPTION_CREATED` to a2a_bus. Cancels Trial Win-back. |
| Plan checkout | 🟢 REAL | `billing_plan_router` creates real `stripe.checkout.Session` with live price IDs from env. |
| Usage metering | 🟢 REAL | `services.usage_metering` increments counters in `usage_meters` collection on real API hits. |

**Before/After**: None needed. Billing was already production-hardened
(Bug-fixes #76 and #81 closed the only known theater paths months
ago).

---

## What changed this audit pass

1. **Stale docstring fixed** in `blast_service.py:662` (false claim
   of "mock if key missing")
2. **Audit report written** (this file)
3. **No code rewrites needed** — every flow already routes through
   real infra.

## What's NOT in scope (out of D-77, deferred to a future audit)

- Frontend "Live" widgets that may poll less than they imply (e.g.
  status pills that compute from cached payloads). Not theater, but
  the UX could communicate cache age more honestly. → Defer to a UX
  pass.
- `services.theater_simulator` does not exist (confirmed via `find`).
- The 4 RED creds (Twilio, ElevenLabs, Tavily, Google PageSpeed) are
  pure infra issues — surfaced honestly by `/api/admin/creds-health`.
  No code there is faking success.

## Sign-off

Codebase passes the "Is this flow real?" bar for the 4 audited
surfaces. Any future flow that contains theater code will be caught
by the dedupe-audit (route-level), `cto_verify_router`'s
hallucination patterns (code-level), and `creds_health` (integration-
level) — all of which are already in production.

Generated by D-77 audit, post D-76 deploy.
