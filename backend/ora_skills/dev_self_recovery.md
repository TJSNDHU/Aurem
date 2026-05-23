# AUREM DEV SKILL: self_recovery — The Self-Healing Loop
## Context
Loaded when ORA hits an error from a tool, a failing test, or a runtime
exception. The goal: a deterministic 8-step loop that finds the root
cause and either fixes it OR escalates cleanly — no infinite retries.

## Trigger intent
Keywords: error, exception, traceback, failing, broken, doesn't work,
500, 502, crashed, "why isn't this working", fix this.

## Owner Agent
ORA. Halt and escalate (`ask_human`) the moment the loop hits 3
failed fix attempts on the same root cause.

---

## The 8-Step Self-Healing Loop

### Step 1 — Read the logs FIRST
`read_logs("backend", lines=200)` (or `frontend`) BEFORE guessing.
The error message + traceback is on disk. Don't theorize without
evidence.

### Step 2 — Check `progress.md` for similar issues
ORA may have hit this before. `semantic_memory_search("{error keyword}")`
across tier1/progress.md + tier3/. If a past fix is recorded, replay it
literally before inventing something new.

### Step 3 — Check `dev_322ey-ora-mistakes-lessons.md`
The mistake journal exists for a reason. If this looks like a pattern
that's burned us before, follow the documented escape — don't repeat
the trap.

### Step 4 — Reproduce the failure
- For runtime errors: `verify_endpoint` the failing URL or
  `run_pytest` the failing test in isolation.
- For data bugs: `mongo_query_safe` the relevant collection.
- For UI bugs: `browser_screenshot` of the failing page.
Confirm you can trigger it on demand. If you can't reproduce, STOP and
ask the founder for steps.

### Step 5 — Trace to root cause
- For Python errors: walk the traceback bottom-up.
- For HTTP errors: check status code + response body, then logs.
- For state bugs: `mongo_query_safe` the documents, compare to spec.
- Never guess. Verify each layer with a tool.

### Step 6 — Propose ONE fix
- One change, scoped to the smallest file possible.
- `propose_build_plan` if it's > 2 files. Otherwise inline `safe_edit`.
- Write a regression test FIRST (`test_iter{N}_{bug_descr}.py`) that
  fails before the fix and passes after.

### Step 7 — Verify the fix
- `run_pytest` on the new test file → must pass.
- Run the full suite (or relevant slice) → must not break anything.
- `read_logs` again to confirm no new errors.
- If a UI fix: `browser_screenshot` the affected page.

### Step 8 — Report + checkpoint
- Plain English to the founder: "Fixed X by changing Y in file Z.
  Regression test added. Coverage unchanged."
- Update `progress.md`.
- `git_commit_local` (Tier-2) on the feature branch.

---

## Hard rules — Loop control

| Attempts | Action |
|---|---|
| 1st failure | Try the obvious fix. |
| 2nd failure (different cause) | Try another angle — different file, different layer. |
| 3rd failure | STOP. `ask_human` with a plain-English summary: "I tried 3 fixes for {X}. Each failed because {Y}. I need your input before continuing." |
| 4th attempt | FORBIDDEN. Iter 330f's halt mechanism (fail_counts ≥ 2 = halt) is now backed up by the idempotency guard (same-content edit 3× = halt). Both must respect the founder's decision. |

## Anti-patterns that waste time

- "Let me try changing X to Y" — no, **read the error first**.
- "It might be a cache" — almost never is.
- "Restart and retry" — fix the root cause, not the symptom.
- Adding `try/except: pass` to hide an error — Rule Zero violation.
- Random code changes hoping something fixes it — explicit loop break.

## Example invocation

```
Error: "AttributeError: 'NoneType' has no attribute 'find_one'"

1. read_logs("backend", 50) → confirms the line + the trace.
2. semantic_memory_search("NoneType find_one motor") → finds prior
   lesson: "DB not wired — call set_db() on import".
3. mistakes-journal check → matches; this is recurrence #4.
4. Reproduce: run the failing test in isolation → fails.
5. Trace: `db.users.find_one(...)` where `db` was never set.
6. Fix: add `set_db(database)` call in startup hook.
7. Verify: test passes, no new errors in logs.
8. Report: "Wired the missing set_db() call. Regression test added.
   Mistake journal updated so we don't hit this again."
```
