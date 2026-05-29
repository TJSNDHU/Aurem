# AUREM Specification Index

> 🛑 **MANDATORY READ for every agent.** Before responding or writing
> code, also process `/app/memory/AGENT_CONTEXT.md` and
> `/app/memory/_README_FIRST.md`. These three files are the
> non-negotiable entry points for any session on this codebase.
>
> **READ THIS FIRST.** Every Emergent / coding agent that touches this
> codebase must read the 6 SPEC documents below before writing or
> changing any code. Order matters — PRD first, Implementation Plan
> last.
>
> Last updated 2026-05-28 (iter D-57)

## The 6 SPEC docs

| # | File | What it answers |
|---|------|------|
| 1 | `SPEC_01_PRD.md`               | WHAT we are building, for WHOM, and WHY. |
| 2 | `SPEC_02_TRD.md`               | HOW we build it technically (stack, infra, third-parties). |
| 3 | `SPEC_03_APP_FLOW.md`          | Every page, button, journey, success/empty/error state. |
| 4 | `SPEC_04_UI_UX_BRIEF.md`       | Visual language — palette, typography, components. |
| 5 | `SPEC_05_BACKEND_SCHEMA.md`    | Every Mongo collection, fields, relationships, indexes. |
| 6 | `SPEC_06_IMPLEMENTATION_PLAN.md` | Phase-by-phase build order; what is shipped vs pending. |

## Reading order for new agents

```
1.  SPEC_INDEX.md             (you are here)
2.  SPEC_01_PRD.md            (vision + scope)
3.  SPEC_02_TRD.md            (stack)
4.  SPEC_03_APP_FLOW.md       (UX)
5.  SPEC_04_UI_UX_BRIEF.md    (visual language)
6.  SPEC_05_BACKEND_SCHEMA.md (data)
7.  SPEC_06_IMPLEMENTATION_PLAN.md (what's done, what's next)
8.  PRD.md / CHANGELOG.md     (live diary — recent iterations)
9.  test_credentials.md       (only when auth work is required)
```

## Live diaries (read AFTER the 6 SPECs)

- `PRD.md`               — append-only iteration log (live changelog)
- `CHANGELOG.md`         — long history (older iters)
- `test_credentials.md`  — current admin / dev creds (read ONLY when editing auth)
- `AGENT_CONTEXT.md`     — sticky rules + Rule Zero + tone
- `WORKING_POLICY.md`    — long-form agent guard rails

## Legacy reference (kept for history — NOT authoritative)

- `ARCHITECTURE.md`     — iter 287.7 (Apr 2026) — Mermaid diagram + 26 services
- `SYSTEM_OVERVIEW.md`  — iter 322fa (May 2026) — 29-tool ORA catalog + Legion Bridge
- `USER_FLOW_MAP.md`    — iter 315e (Apr 2026) — customer/admin flows complement SPEC_03
- `SYSTEM_MAP.md`       — DB collections + endpoint inventory (superseded by SPEC_05)
- `COMPLETE_SUMMARY.md` — earlier session summaries
- All `_archive/` + `tier1/` + `tier2/` + `tier3/` — frozen snapshots

## Rule Zero (un-negotiable)

- Plain English. 1–3 sentences in chat. No JSON / no tracebacks / no code dumps.
- Empathy + patience — the founder has been burned before.
- Hinglish (Hindi + English) when the founder uses it.
- Never invent SHAs, dates, iter tags, or endpoints — see the D-57
  GUARDRAIL system prompt in `services/dev_cto_chat.py`.
