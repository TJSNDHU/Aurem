---
name: dev_code-refactoring
description: "AUREM-specific code refactoring skill — wired into ORA CTO toolset, scoped to /app/backend (FastAPI) and /app/frontend/src (React)."
risk: high
source: aurem_internal
date_added: "2026-02-15"
---

# AUREM SKILL: code-refactoring

## Context

This skill is invoked when ORA refactors AUREM platform code. Unlike the
community refactoring template this replaces, every action is wired
through the ORA CTO toolset and respects AUREM's governance gates.

**Stack:** FastAPI (Python 3.11) + React 19 + MongoDB (Motor async) on
Emergent / Kubernetes.

**Write-allowed roots:** `/app/backend`, `/app/frontend/src`,
`/app/memory`, `/app/ora_skills`, `/app/scripts`.

**Forbidden paths** (`safe_edit` refuses): `.env`, `package.json`,
`requirements.txt`, lock files, `.git/`, `build/`.

## Trigger intent

User asks to fix, build, debug, test, refactor, review, or improve
AUREM code. Keywords: `fix`, `bug`, `refactor`, `clean up`, `simplify`,
`extract`, `dedupe`, `improve`, `optimize`, `tighten`.

## Owner agent

None — ORA handles dev tasks directly. Council layer (peer_review,
code_review, security_scan, council_consult) is mandatory for
auth/payment/schema refactors.

---

## Use this skill when

- Reducing duplication or cyclomatic complexity in a FastAPI router /
  service module that the tools registry can read.
- Splitting a `server.py`-grown router into a per-resource file under
  `/app/backend/routers/`.
- Moving inline business logic from a router into a `/app/backend/services/`
  module to make it unit-testable from `/app/backend/tests/`.
- Tightening up React components (`/app/frontend/src/components/`) by
  hoisting hooks, memoising, or removing dead props — keeping `data-testid`
  attributes intact (REQUIRED by the testing-agent contract).
- Replacing per-request `MongoClient()` instances with the shared
  `server.db` motor handle (recurring Bug-98/127 pattern).

## Do not use this skill when

- The change is a one-line typo / log fix. Just `safe_edit` it.
- The request is a new feature. Use the build skill, not refactoring.
- The file is on the forbidden-write list. Escalate.
- The user is in a change freeze window (check
  `aurem_freeze` collection — `active=true` means STOP).

---

## Mandatory pre-refactor checks (in order)

1. **`grep_codebase`** — find every caller of the function/class you're
   about to touch. If callers exist in files outside the write-allowed
   roots, escalate.
2. **`code_review`** on the file. Score must be ≥ 70 to proceed; quote
   any `[critical]` or `[high]` issues in your plan.
3. **`security_scan`** if the file path matches any of:
   - `auth`, `jwt`, `oauth`, `bcrypt`, `password`
   - `billing`, `stripe`, `payment`, `subscription`, `checkout`
   - `admin`, `dashboard`, `audit`
   - any `routers/` or `services/` file with `_router.py` / `_service.py`
     suffix touching those concerns
   Risk score > 80 → do NOT refactor; escalate with the vuln list.
4. **`council_consult`** with at least `security` + `backend` if the
   file is on the security-sensitive list above OR touches Mongo
   schema. Roles auto-select on `safe_edit_with_council` but you can
   pre-run a consult to fail fast.

If any check fails: stop, report the failure with real tool output,
escalate to founder. Do not edit.

---

## Refactor execution

Use **`safe_edit_with_council`** — NEVER bare `safe_edit` for production
code. Required args:

- `path`: under write-allowed roots
- `find_string`: exact, whitespace-sensitive
- `replace_string`: the new code
- `expected_occurrences`: pin to the count you read from grep; fails
  loudly if reality differs
- `rationale`: ≥ 10 chars — what is this refactor doing?
- `roles`: optional; defaults to risk-tier auto-select

For large refactors split into **small slices**, one `safe_edit_with_council`
per logical hunk so each is independently revertible from `/tmp/ora_backups/`.

After every slice:

1. `lint_python` on the changed file — must pass.
2. If backend code changed: `restart_service` → `health_check` (poll
   until HTTP 200).
3. `pytest_run` on the relevant test file under `/app/backend/tests/`.
   No new failures.
4. `curl_internal` exercises any endpoint whose handler you edited.

---

## Post-refactor — proof artefacts (required)

Before reporting "refactor complete", produce three proofs:

1. **Diff** — the `git diff` summary from `safe_edit_with_council`.
2. **Test result** — `pytest_run` output: `N passed, 0 failed`.
3. **Health check** — `health_check` returning `200`.

For commit: `propose_commit` with `title` = conventional-commit summary
(`refactor: <scope>: <change>`) and rationale ≥ 10 chars. Founder
approves via `/admin/git-gate`.

---

## AUREM anti-patterns to surface during refactor

| Pattern | Fix |
|---|---|
| `from pymongo import MongoClient` in a request handler | Replace with shared async `from server import db` |
| `datetime.utcnow()` | Replace with `datetime.now(timezone.utc)` |
| Returning Mongo docs with `_id` field | Add `{"_id": 0}` projection |
| `if x and x.startswith("Bearer ")` reimplementation | Use shared `utils.require_auth.require_auth` / `require_admin` |
| `if payload.get("email")` as an auth gate | Bug pattern — replace with `is_admin_email` whitelist |
| Hardcoded JWT or admin-key defaults | Read from env, fail fast if missing |
| Per-router `_verify_token` that skips role check | Use shared helper |
| `httpx.AsyncClient` GETting user-supplied URLs | Add `routers.intelligence_router._block_ssrf(url)` first |
| `git commit` / `git push` invoked directly | Forbidden — use `propose_commit` |
| Mock data returned by a service | Flag in PRD — mocked features must be highlighted in `finish` |

---

## Safety

- Never change external API contract (routes, request/response shapes)
  without an explicit founder OK.
- Keep `data-testid` attributes on every interactive element in JSX
  edits — testing agent depends on them.
- Keep diffs small enough to review in one screen. If a refactor
  needs > 200 lines of diff, split it into multiple proposals.
- If lint or tests regress, revert from `/tmp/ora_backups/` and
  escalate. Do not chase green by patching tests.

## Output format (when reporting to founder)

1. **Summary of issues** found by `code_review` + `security_scan`.
2. **Refactor plan** — ordered slices, each ≤ 1 file ≤ 50 LOC change.
3. **Proposed changes** — diff summary per slice.
4. **Test / verification** — pytest + curl + health-check evidence.
5. **Commit proposal ID** — the `ora_commit_proposals` document ID.

## Limitations

- This skill is scoped to AUREM monorepo paths. Do not apply to
  customer code under `/mnt/uploads/`.
- Do not refactor across the FastAPI / React boundary in a single
  proposal — split into two so the council can review each side
  separately.
- Stop and ask if the desired post-refactor behaviour is ambiguous.
