# 🛑 STOP — READ THIS FIRST 🛑

> **Every agent / Emergent fork / coding assistant** that opens this
> repository MUST read these two files before responding to anything:
>
>   1. `/app/memory/AGENT_CONTEXT.md`   ← sticky rules + Rule Zero + tone
>   2. `/app/memory/SPEC_INDEX.md`      ← gateway to the 6 SPEC docs
>
> Skipping this step has historically cost the founder hours of rework
> and trust. Do not skip.

---

## TL;DR for the next agent

- **Founder**: Tejinder Sandhu, Polaris Built Inc., Mississauga, Ontario.
- **App**: AUREM — Autonomous Business Operating System for Canadian SMBs.
- **Current iter**: D-57 (as of 2026-05-28).
- **Tests**: 166 / 166 pytest green across the active D-40b → D-57 ring.
- **Language**: respond in Hinglish (Hindi + English) when the founder
  writes in Hinglish. 1–3 sentences. No JSON / no code blocks / no
  tracebacks in chat. ("Rule Zero")
- **Production**: `https://aurem.live` (Hetzner FSN1 + Cloudflare).
  Preview environment is separate; preview Mongo ≠ prod Mongo.
- **NEVER fabricate**: commit SHAs, dates, iter tags, API endpoints,
  file line numbers, deploy results. If you don't have the real value,
  say "I need to look that up" and use the D-54 codebase reader or
  D-52 verification probes.

## The 6-doc reading order

```
1. AGENT_CONTEXT.md             (sticky rules, this is mandatory)
2. SPEC_INDEX.md                (links to all 6 SPEC docs)
3. SPEC_01_PRD.md               (vision + scope + personas)
4. SPEC_02_TRD.md               (stack + auth + integrations)
5. SPEC_03_APP_FLOW.md          (founder + dev surfaces, D-57 era)
6. SPEC_04_UI_UX_BRIEF.md       (design language)
7. SPEC_05_BACKEND_SCHEMA.md    (Mongo collections + indexes)
8. SPEC_06_IMPLEMENTATION_PLAN.md (what's shipped, what's pending)
9. PRD.md / CHANGELOG.md        (live diary — recent iterations)
10. test_credentials.md         (only when editing auth)
```

## Hot-button rules (most-violated, do not regress)

1. **All API routes prefixed `/api`** — Kubernetes ingress requires it.
2. **Mongo `_id` MUST be excluded** in every response (`{"_id": 0}`).
3. **All secrets / URLs from `.env`** — never hardcode, fail-fast on missing.
4. **AUTH is always an integration** — call `integration_playbook_expert_v2`
   BEFORE writing any auth code.
5. **Never claim "sent ✅" without system verification** — D-52 / D-57
   surface RED when a delivery actually failed.
6. **One smoke screenshot only** — no implement → screenshot →
   implement loops. Trust your code; let the testing agent verify.

---

**This file (`_README_FIRST.md`) lives at the top of `/app/memory/`
so any directory listing or LLM context-loading sweep encounters it
first.** When forking a session, copy the TL;DR block above verbatim
into the handoff summary's line 1.
