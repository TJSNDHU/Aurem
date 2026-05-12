# AUREM SKILL: ora-cto-final-complete (iter 322es)

## Status: 100% COMPLETE — no broken ends, no half-done features

This skill records the FINAL state of the ORA CTO autonomous stack after
the iter 322es completion sweep. ORA can now do the full preview →
deploy → save-to-GitHub → rollback cycle from a single chat window.

## What ORA can do now (17 tools)

### Read-only (no side effects)
- `grep_codebase` — fast ripgrep wrapper
- `view_file` — paginated file read
- `view_dir` — directory listing
- `curl_internal` — hit any /api/* endpoint with founder JWT
- `db_count` — count documents in any Mongo collection
- `db_distinct` — distinct values for a field
- `git_log` — recent commit history
- `health_check` — `/api/platform/health`
- `lint_python` — ruff on a file (read-only)

### Execute / write
- `shell_exec` — whitelisted shell commands (ls, find, wc, stat, git read,
  echo, head, tail, grep — never rm/dd/mv/cp/curl-external)
- `safe_edit` — atomic find-and-replace with `.bak` snapshot to
  `/tmp/ora_backups/`
- `restart_service` — supervisor restart for backend / frontend

### Council (peer review)
- `peer_review` — single specialist (security / backend / qa / devops /
  design / finance / marketing / pricing)
- `code_review` — wraps AUREMCodeReviewer over a file
- `security_scan` — OWASP top-10 scan over a path
- `council_consult` — parallel multi-peer fan-out (≤5 peers)

### Governance gates (iter 322eq + 322er)
- `safe_edit_with_council` — REJECTS the edit if any peer dissents
  (DO NOT / STOP / CRITICAL). Override requires `override_dissent=True`
  AND `override_reason ≥20 chars`. Loud-logged to
  `ora_governance_overrides`.
- `shell_exec_with_council` — same gate for high-risk shell argv (rm,
  dd, drop, mkfs).
- `propose_commit` — record a commit proposal. ORA cannot actually
  commit; founder approves via `/api/admin/git-gate/proposals/{id}/approve`.

## What the founder can do in the admin UI

- `/admin/ora-chat` — 3 tabs:
  - **General Chat** — converse with ORA via `/api/public/ora/chat`
  - **CTO Mode** — quick action buttons (12 tools), live tool output
    pane, recent invocations side bar, rollback panel listing last 10
    safe_edit backups with one-click restore, **PREVIEW / DEPLOY / SAVE
    TO GITHUB** workflow exposed inline after each tool execution
  - **Files & Uploads** — drag-drop PDF / DOCX / TXT / MD / JPG / PNG /
    MP3 / MP4 (≤30 MB) into `/mnt/uploads/{tenant_id}/`, with
    "Analyze with ORA" button per file
- `/admin/ora-cto` — read-only cockpit (5 KPI tiles, per-tool rollup,
  council override trail, paginated invocations feed)
- `/admin/git-gate` — pending commit proposals + colorized diff
  preview + Approve / Reject / Reject+revert
- `/admin/ora-settings` — 5 sections:
  - GitHub Integration (PAT + repo + branch protection + test connection)
  - Permissions (toggle each of the 17 tools, shell whitelist editor)
  - Council (peer roles, hard gate ON/OFF, vote threshold)
  - Notifications (WhatsApp critical, email digest time)
  - Audit & Logs (retention days, export CSV, view cockpit/rollbacks)
- `/admin/ora-optimize` — codeburn-pattern LLM budget watchdog
- `/admin/design-extract` — DTCG / Tailwind / shadcn token extractor

## How the Preview → Deploy → Save → Rollback flow works

1. **Preview**: founder picks a tool in CTO Mode, edits args, clicks
   "Execute (PREVIEW)". The tool runs in the actual environment and
   returns full output. If it was a `safe_edit_with_council`, a `.bak`
   is written to `/tmp/ora_backups/` BEFORE the file is replaced.
2. **Deploy**: founder clicks "Deploy: lint → restart → health". UI
   chains `lint_python` → `restart_service` → `health_check` and
   surfaces each step's outcome.
3. **Save to GitHub**: founder clicks "Save to GitHub". UI calls
   `propose_commit` and redirects to `/admin/git-gate`. Founder reviews
   the colorized diff and clicks Approve to make the REAL `git commit`
   (author: ORA Sovereign CTO).
4. **Rollback**: rollback panel in CTO Mode lists the last 10 `.bak`
   files. One click → `/api/admin/ora-rollback/restore` → atomic file
   replacement + service restart + audit log entry.

## What we deliberately do NOT track

- **Per-tool LLM cost** — AUREM is self-hosted; the founder doesn't
  meter himself. Customer plans are flat-rate.
- **Per-session quotas** — ORA operates without rate limits. Safety
  comes from the council gate (any peer can REJECT) and the git commit
  gate (founder approves every commit).

## Three-proof completion verdict

1. `/api/admin/{ora-cto,git-gate,ora-files,ora-settings,ora-rollback}/_/health`
   ALL return HTTP 200.
2. `ora_tool_invocations` collection grows in real time as the founder
   exercises tools. `ora_commit_proposals` records every founder-
   approved commit with the real SHA.
3. `git log --oneline -3` shows the `ORA (Sovereign CTO) <ora@aurem.live>`
   commits made via the git gate (verified: `c3ff792`).

## Why this matters

Before iter 322es, ORA had powerful tools but the founder had to
SSH/curl to invoke them. Now everything happens in `/admin/ora-chat`:
ORA proposes a change → founder previews + approves → real change
deploys + lands in the repo. The full developer cycle in one window,
with hard rollback always one click away.

---
**Author**: AUREM main agent (iter 322es)
**Enforcement**: Permanent. This is the canonical ORA CTO surface. All
  future ORA features extend from `/admin/ora-chat` or one of the
  dedicated admin pages above.
