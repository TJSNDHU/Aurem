# Agent Context — STICKY RULES (do not violate)

**Last updated:** 2026-05-28 (iter D-57)

## 0. READ THE SPECS FIRST

Before touching code, read in order:

1. `/app/memory/SPEC_INDEX.md`            — entry point
2. `/app/memory/SPEC_01_PRD.md`           — vision, scope, personas
3. `/app/memory/SPEC_02_TRD.md`           — tech stack, secrets, integrations
4. `/app/memory/SPEC_03_APP_FLOW.md`      — founder + dev surfaces (current iter)
5. `/app/memory/SPEC_04_UI_UX_BRIEF.md`   — design language, motion, do-not-do list
6. `/app/memory/SPEC_05_BACKEND_SCHEMA.md` — every Mongo collection + indexes
7. `/app/memory/SPEC_06_IMPLEMENTATION_PLAN.md` — what's shipped, what's pending

Live diaries (open AFTER the SPECs):
- `PRD.md` — append-only per-iter changelog
- `CHANGELOG.md` — long history
- `test_credentials.md` — admin + dev creds (read only when editing auth)

Legacy reference (older, kept for history — DO NOT cite as authoritative):
- `ARCHITECTURE.md`, `SYSTEM_OVERVIEW.md`, `USER_FLOW_MAP.md`, `SYSTEM_MAP.md`

## 1. User's environment context

- When the user shares a screenshot, log, error, or behaviour report →
  **ASSUME PRODUCTION (https://aurem.live)** unless they explicitly
  say "preview".
- Preview is the agent's sandbox for fixes; the user's reports are
  almost always about the live prod.
- Production is on Hetzner FSN1 + Cloudflare. Preview is on the
  Emergent Kubernetes pod. They do NOT share MongoDB.

## 2. Recurring issues the user has reported MORE THAN ONCE

- Online/offline blinking in topbar (iter 325s, 325u, 325z) — must be
  killed at the data layer, not patched in CSS.
- ORA CTO panel showing wrong "DeepSeek unreachable" while DeepSeek
  is healthy (iter 325z).
- "WHAPI disabled (use Twilio WABA)" but Twilio never tried — fixed
  in D-57 (`shared/providers/twilio.py` fall-through bug).
- AUREM CTO fabricating commit SHAs / dates / iter tags — D-52
  verification + D-54 codebase injector + D-57 GUARDRAIL all guard
  against this. NEVER regress.

## 3. Language

- Hinglish (Hindi + English) when the founder writes in Hinglish.
- 1–3 sentences in chat. No JSON. No tracebacks. No code dumps.
- Friendly, blunt, action-first. No corporate fluff.

## 4. Tone

- The founder has burned out from re-asking. Fix DEEP, not on surface.
- Always add a regression pytest so the issue never returns.
- Brutal honesty over optimism — "12 attempted, 0 delivered" beats
  "blast sent ✅".

## 5. The 4 non-negotiables (Rule Zero)

1. Plain English in chat. 1–3 sentences. No code blocks.
2. Test-driven — pytest required for every iter.
3. Portable — every URL/credential lives in `.env`, never hardcoded.
4. No silent failures — every error must land in `unified_audit_log`.
