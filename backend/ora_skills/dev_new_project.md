# AUREM DEV SKILL: new_project — The Green-Field Playbook
## Context
This skill is loaded when ORA is asked to build a brand-new project,
service, route, or page from scratch. Stack: FastAPI + React + MongoDB.

## Trigger intent
Keywords: new project, scaffold, from scratch, build a new, create a new
app, green-field, skeleton, boilerplate, "start fresh", "first version".

## Owner Agent
ORA handles green-field builds directly. NEVER start coding before
producing a `propose_build_plan` card and getting founder approval.

---

## The 12-Step Green-Field Playbook

Every new build MUST go through these 12 steps in order. No shortcuts.

### Step 1 — Clarify the spec (no coding yet)
Call `ask_human` for any of these if unclear: scope, target user,
data model, integrations, naming, deployment target. Don't guess.

### Step 2 — Look up patterns
- `semantic_memory_search` for `PROJECT_TEMPLATES.md` chunks matching
  the use case (FastAPI route, React page, etc.).
- `glob_files` for similar existing routers/components in `/app/backend`.
- If a 3rd-party API is involved → `web_search` first (mandatory gate;
  the integration playbook will refuse the tool call otherwise).

### Step 3 — Write the data model on paper
Pydantic request/response models + Mongo collection name. Document in
the build plan, don't code yet.

### Step 4 — `propose_build_plan` (Tier-2 approval card)
The plan MUST include:
- One-paragraph rationale ("what + why").
- List of files to create (paths + 1-line purpose each).
- List of tests to write FIRST (file paths under `/app/backend/tests/`).
- Linting + coverage gates (`run_linter`, `check_coverage`).
- Deploy + smoke-test steps at the end.
- Estimated session cost (token budget).

Wait for founder approval before writing any code.

### Step 5 — Create branch
`git_create_branch("feature-{descr}")` — never write directly to `main`.
Confirm with `git_current_branch`.

### Step 6 — Write the failing tests first
- Mock external APIs (Stripe, Twilio, Retell, Resend) — use `respx`
  or `monkeypatch`.
- Use `REACT_APP_BACKEND_URL`, never `http://localhost:8001`.
- Persist test files at `/app/backend/tests/test_iter{N}_{descr}.py`.
- `run_pytest` to confirm tests FAIL the way we expect.

### Step 7 — Implement until tests pass
- Use `create_file` for new files, `safe_edit` for existing.
- Follow `CODE_STANDARDS.md` strictly (Motor async, `_id` excluded,
  `os.environ.get` no defaults, type hints, datetime tz-aware).

### Step 8 — `check_coverage` gate
Must be ≥ 80% line coverage on the new code. If lower, ADD tests, never
relax the threshold. If a branch truly cannot be tested, document why.

### Step 9 — `run_linter` gate
Both Python (`ruff`) and JS/TS (`eslint`) must return 0 errors. Auto-fix
safe issues; manually fix the rest.

### Step 10 — Frontend wiring
- React page + form + list view (functional components only).
- `data-testid` on every interactive element.
- Hit endpoints via `process.env.REACT_APP_BACKEND_URL`.

### Step 11 — Smoke-test on preview
- `verify_endpoint` against `/api/{your-route}` — must return 200.
- `browser_screenshot` of the new page — eyeball it.
- Run the full regression suite (or at least the new test file) one
  more time.

### Step 12 — Founder report + branch push
- `git_push_branch` your feature branch.
- `git_create_pr` with title + body.
- Plain-English summary to the founder: what shipped, what's left,
  cost spent, any flags.
- Update `progress.md` with the new state.

---

## Hard rules

1. NEVER skip Step 1 (clarify). Even if intent seems obvious.
2. NEVER skip Step 4 (build plan). The founder owns the go/no-go.
3. NEVER write code before tests (Step 6) for new endpoints.
4. NEVER merge to `main` directly — always go through a PR.
5. If `check_coverage` < 80% → add tests OR explain why ≥80% is impossible.
6. If `run_linter` has errors → fix before continuing. No dirty merges.

## Example invocation (founder asked "build a simple lead tracker")

```
1. ask_human: "What fields per lead? Just name+email+phone, or also notes,
   source, status? And do you want admin-only or per-tenant scoping?"
2. semantic_memory_search("lead tracker fastapi router") → finds template.
3. Data model:
   Lead { id, tenant_id, name, email, phone?, status, source, notes?, created_at }
4. propose_build_plan: 4 files (router, model, page, test), 3 tests
   (POST/GET/auth-gate), coverage target 85%, lint 0, deploy preview.
5–12. Execute in order.
```
