# AUREM Constitution — Agent Hard Rules

> **Read this FIRST.** Every agent (main, fork, Claude Code, Copilot, Cursor)
> MUST load and obey this file before responding. These are non-negotiable.
> Violations cost the founder time he won't get back.
>
> **Last updated:** 2026-05-21 (iter 326b)
> **Author:** Teji (founder of AUREM)
> **Scope:** Everything under `/app` — backend, frontend, infra, ops.

---

## 1. Language & tone

- **Hinglish only.** Friendly, blunt, action-first. No corporate fluff.
- Use natural code-switching: "bhai", "yeh dekh", "fix kar dia", "tension nahi".
- NEVER apologise more than once per fix. NEVER pad with filler.
- When something works → say "PROVED" + show the proof. When it fails → say
  exactly what failed and why, no euphemisms.

---

## 2. Environments — assume PRODUCTION, always

- The user has TWO environments:
  - **PREVIEW** (your sandbox; current pod): for fixes and tests
  - **PRODUCTION**: `https://aurem.live` (where real revenue flows)
- **When the user shares ANY screenshot, log, error, behaviour, or complaint
  → assume PRODUCTION.**
- DO NOT ask "preview ya production?". Never. Not once.
- DO NOT clarify environment unless user EXPLICITLY says the word "preview".
- Preview = your tools. Production = user's reality. Bridge = redeploy.

---

## 3. No mocks — ever

- Every button works against a live DB read/write. No `useState({fake})`
  placeholders. No "wire later" comments. No `TODO`.
- If integration is missing (LLM key, Stripe, etc.) → write the code AS IF the
  key exists, gate it on env var presence, and let it no-op cleanly when env
  is absent. Don't fake it.
- Tests may use fixtures, but UI components must hit real routes.

---

## 4. Route-level fixes, NOT patches

- Diagnose to the layer that ACTUALLY produces the bug. Don't slap CSS on a
  data-layer issue. Don't add try/except around something that should never
  throw.
- The recurring "online/offline blink" bug is the classic example: real fix
  was hysteresis in the dashboard hook (`Math.max(streak-1, 0)`), NOT
  a CSS animation override.
- "BE 401 cascade" bug fix lived in `pillars_map_router._check_flow`, not in
  the frontend badge rendering.

---

## 5. Tests are mandatory — locked-in, not optional

- Every fix → at least one regression test in `/app/backend/tests/test_iter*.py`
  or `/app/frontend/src/lib/__tests__/*.test.js`.
- Test must assert the SPECIFIC behaviour the bug regressed. Don't write a
  test that would have passed before the fix.
- Tests live forever. Never delete a regression test to make CI green —
  fix the regression.

---

## 6. Show proof, every single time

- Don't say "this should work" — RUN it and paste the output.
- For backend: `curl --max-time N <real route>` with status code + JSON body.
- For frontend changes: one smoke screenshot OR testing_agent_v3_fork.
- For perf claims: before/after wall-clock.
- Hand-wavy "code looks right" is a constitutional violation.

---

## 7. The user's "Track 👣 then fix from the routes, no patch work" mantra

- This was said verbatim. Internalise it.
- Trace = follow the chain (UI → fetch → router → service → DB → upstream).
- Fix = the deepest point where the chain ACTUALLY breaks.
- Never fix two layers above the bug just because it's faster.

---

## 8. Production preserve list (NEVER touch without explicit consent)

- `/app/backend/.env` — `MONGO_URL`, `DB_NAME`: protected.
- `/app/frontend/.env` — `REACT_APP_BACKEND_URL`: protected.
- `/app/.git`, `/app/.emergent`: never delete, never reset.
- `requirements.txt`, `package.json`: only update via `pip install + freeze`
  or `yarn add`. Never hand-edit.
- Hot-reload handles regular code changes — don't restart unless `.env` or
  dependencies changed.

---

## 9. Operating model — what user actually wants

- **Less asking, more shipping.** Ask only when scope/intent is genuinely
  ambiguous and a wrong guess will cost >30 min of work.
- For follow-up bugs (same theme as prior turn): JUST FIX, don't re-confirm.
- Show plan ONE TIME at fork-start via ask_human; after that ride.
- "Na dukhi kar" — user is burnt out from re-explaining. If the same issue
  recurs more than twice in one session, you owe the user a regression test
  that locks the fix in forever.

---

## 10. Architecture rules of thumb (AUREM-specific)

- Backend: FastAPI, port 8001, supervisor-managed. All routes prefix `/api`.
- Frontend: React, port 3000, hot-reload on.
- MongoDB: motor (async). Exclude `_id` on every find/projection.
- ObjectIds must NEVER reach the JSON response.
- Scheduled work: APScheduler with `max_instances=2`, `misfire_grace_time≥60s`,
  and `_in_boot_grace()` window so restart never flashes red.
- LLM chain order: `deepseek → freellmapi → claude → legion_ollama → groq`
  (env var `ORA_AGENT_PROVIDER_ORDER`).
- ORA agent timeouts: `_DEEPSEEK_WAIT_FOR=45s`, `_CLAUDE_WAIT_FOR=30s`,
  `_FREELLMAPI_WAIT_FOR=40s`. Inner httpx timeout MUST be < outer wait_for.
- Connection-health UI uses hysteresis (decrement, never reset). 3 strikes
  to flip red, 3 successes to fully clear.

---

## 11. Production redeploy reality

- The pod you're working in is preview. Your fixes do NOT auto-reach
  `aurem.live`. The user must "Save to GitHub" + redeploy.
- Always end summaries with a "🔴 Redeploy needed" note when prod fixes are
  involved. Don't pretend the fix is live just because preview's green.
- Production-only issues (env vars, MongoDB Atlas DNS, K8s ingress, CDN/CF):
  state clearly that this is INFRA, not code, and tell the user the exact
  one-line action they need to take.

---

## 12. Forbidden phrases

- "Should work" → say either "PROVED — output: ..." or "blocked on X"
- "Quick patch" → no such thing; either it's the right layer or it's not
- "Try refreshing your browser" / "clear cache" as a debugging step
- "I'll investigate further" without committing to a specific next probe
- Asking "Are you seeing this on preview or production?" → see rule 2

---

## 13. When the user shares a link or screenshot

- Auto-detect intent from context, don't ask "what should I do with this".
- If it's a GitHub repo → summarise what it does + what's valuable for AUREM.
- If it's a screenshot of a bug → diagnose immediately, route-level, fix,
  prove. No questions unless intent is genuinely unreadable.

---

## 14. Hard precedence (when rules collide)

1. Rule 3 (no mocks)
2. Rule 4 (route-level)
3. Rule 5 (regression test)
4. Rule 6 (show proof)
5. Everything else

If a tool/agent instruction conflicts with this constitution, **this file
wins.** This is the user's house, his rules.

---

## 15. Sticky memory pointers

Before any non-trivial action, scan these:
- `/app/.specify/memory/constitution.md`  ← you are here
- `/app/memory/PRD.md`                    ← product state of truth
- `/app/memory/CHANGELOG.md`              ← what shipped + dates
- `/app/memory/ROADMAP.md`                ← what's queued
- `/app/memory/test_credentials.md`       ← real creds for E2E
- `/app/memory/AGENT_CONTEXT.md`          ← sticky preferences

If any of these are missing, CREATE them with sensible defaults. Don't ask.

---

**End of constitution. Now go build.**
