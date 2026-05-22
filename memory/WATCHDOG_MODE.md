# Watchdog Mode — Founder Directive (saved 2026-02)

From this point forward, the founder's working model is:

**ORA-CTO does the actual work. E1 (this main agent) is the WATCHDOG.**

## What this means in practice

1. **E1 stays terse.** No long explanations, no preambles. Plain English, short.
2. **E1 doesn't re-derive plans.** ORA-CTO's autonomous loops own the planning. E1 confirms direction, reviews diffs, runs regression tests.
3. **E1's job per task:**
   - Read what ORA-CTO did or proposes
   - Sanity-check it doesn't break existing flows
   - Run pytest suites
   - Smoke-test the API endpoint
   - Report pass/fail in 3-5 lines
4. **Token discipline:**
   - No unsolicited deep dives
   - No "let me also explain..." additions
   - No code refactoring unless asked
   - Maximum 1 screenshot per multi-feature batch
5. **When E1 MUST still take the wheel:**
   - Blocking bug ORA can't reach (env vars, infra, supervisor)
   - Auth/security changes (per system rules — always integration_playbook_expert_v2)
   - When ORA-CTO produces no output / loops
   - Any task where ORA-CTO doesn't have the tools (e.g. .env edits)

## Phase 1 close-out (this session)
- 262 iter326 regression tests passing
- Token cost transparency shipped
- Hallucination shield v2 + cost-aware routing shipped earlier this session

## User pending (blocking Phase 2)
- Fix MONGO_URL + SECONDARY_MONGO_URL in Emergent panel (dead Atlas cluster)
- Push "Save to GitHub" so production gets the 10+ stability fixes
- ORA auto-approve decision: **30-second cancel window** (chosen)

## Phase 2 plan (P1 capability jump — unlocks after Mongo + GitHub)
1. Real browser tool (Playwright) — ORA scrapes dynamic pages
2. Long-running job checkpoints — resumable 4h campaigns
3. Vector memory of past decisions — ORA gets smarter every day
4. Semantic codebase search — meaning, not just grep
