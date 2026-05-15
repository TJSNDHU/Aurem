# AUREM SKILL: ora-cto-final-complete (CANONICAL — iter 322eu+)

## Status: 100% LIVE — 35 tools in the registry as of 2026-02

This is the **canonical source of truth** for the ORA CTO autonomous
stack. Older docs (`dev_ora-cto-peer-council.md`) are superseded by this
file and remain only for the council-workflow detail.

> **How to verify the tool count yourself:**
> ```bash
> cd /app/backend && python3 -c "from services.ora_tools import TOOL_REGISTRY; print(len(TOOL_REGISTRY))"
> ```
> If this number diverges from the count in this file, update this file —
> never invent tools that aren't in the registry.

---

## The 35 tools — what's actually registered

### Read-only (8)

| Tool | What it does |
|---|---|
| `grep_codebase` | ripgrep wrapper over `/app/{backend,frontend,memory,ora_skills}` |
| `view_file` | paginated file read with `start` + `max_lines` |
| `view_dir` | directory listing (name/type/bytes) |
| `curl_internal` | GET an `/api/*` endpoint on `localhost:8001` |
| `db_count` | Mongo `count_documents` on allow-listed collections |
| `db_distinct` | Mongo `distinct()` for a field |
| `git_log` | recent commits on `/app` |
| `health_check` | hit `/api/platform/health` |

### Lint / static (1)

| Tool | What it does |
|---|---|
| `lint_python` | `ruff check` on a `.py` file — read-only, no `--fix` |

### Execute (4)

| Tool | What it does |
|---|---|
| `shell_exec` | whitelisted argv-only subprocess (`whoami`, `id`, `pwd`, `hostname`, `uname`, `uptime`, `date`, `env`, `ls`, `find`, `wc`, `stat`, `du`, `file`, `df`, `free`, `ps`, `which`, `whereis`, `node --version`, `pip list`, `yarn --version`, `ruff`, `git log/status/diff/show/branch`, `supervisorctl status`) |
| `restart_service` | `supervisorctl restart backend` / `frontend` only |
| `legion_exec` | Legion-laptop reverse-poll proxy execution |
| `docker_compose` | local-only compose orchestration |

### Write (3)

| Tool | What it does |
|---|---|
| `safe_edit` | atomic find-and-replace, `.bak` snapshot to `/tmp/ora_backups/`, refuses if `expected_occurrences` doesn't match |
| `create_file` | new file under write-allowed roots, max 200 KB |
| `create_dir` | new directory under write-allowed roots |
| `append_to_file` | append-only write (e.g. PRD/CHANGELOG) |

### Council — peer / static review (4)

| Tool | What it does | Cost |
|---|---|---|
| `peer_review` | single-role LLM specialist (security / backend / devops / qa / design / finance / marketing / pricing) — loads `agent_<role>.md` as system prompt | LLM |
| `code_review` | deterministic `AUREMCodeReviewer` static scan — FastAPI patterns, React hooks, Mongo anti-patterns, OWASP | 0 |
| `security_scan` | deterministic `AUREMSecurityScanner` — OWASP Top 10 + SaaS-specific (auth/payment/billing) + Mongo injection + XSS/CSRF | 0 |
| `council_consult` | parallel fan-out to ≤5 peers, returns all opinions side-by-side | LLM × N |

### Governance gates (3) — wrap a write tool with a council vote

| Tool | What it does |
|---|---|
| `safe_edit_with_council` | `safe_edit` + auto-selected peer roles by path risk. REJECTS on `STOP` / `DO NOT` / `CRITICAL` from any peer. Override requires `override_dissent=True` + `override_reason` ≥20 chars. Loud-logged to `ora_governance_overrides`. |
| `shell_exec_with_council` | `shell_exec` + peer review when argv contains `rm`, `dd`, `drop`, `mkfs`. Same override discipline. |
| `propose_commit` | record a commit proposal in `ora_commit_proposals`. ORA cannot `git commit` directly; founder approves via `/api/admin/git-gate/proposals/{id}/approve`. |

### Git (3)

| Tool | What it does |
|---|---|
| `git_log` | (also listed under Read-only) |
| `git_bisect` | bisect a regression range — read-only, no checkouts |
| `git_commit_local` | local commit (no push) — only after `propose_commit` is founder-approved |

### Infrastructure (4)

| Tool | What it does |
|---|---|
| `cloudflare_dns_list` | read DNS records via Cloudflare API |
| `cloudflare_dns_write` | write/update DNS records — governance-gated |
| `pip_propose` | propose a `pip install <pkg>` for founder approval (frozen lockfile gate) |
| `pytest_run` | run pytest under `/app/backend/tests/` |

### Business engines (5)

| Tool | What it does |
|---|---|
| `campaign_status` | auto-blast pipeline state |
| `force_blast_cycle` | trigger one Auto-Blast cycle for a tenant |
| `channel_gating_reseed` | reseed channel-gating MongoDB doc |
| `claim_build_done` | mark a Builder build complete |
| `ora_run_natural` | natural-language entrypoint that routes to the tools above |

**Count: 35.** If you can think of a tool not on this list, run the
verification snippet above before claiming it exists.

---

## What the founder controls (admin UI)

- **`/admin/ora-chat`** — General Chat + CTO Mode + Files & Uploads (PDF/DOCX/TXT/MD/JPG/PNG/MP3/MP4 ≤ 30 MB). CTO Mode has live tool I/O, recent-invocation sidebar, rollback panel for last 10 `.bak` files, **PREVIEW / DEPLOY / SAVE TO GITHUB** inline.
- **`/admin/ora-cto`** — read-only cockpit (5 KPI tiles, per-tool rollup, council override trail, paginated invocations feed).
- **`/admin/git-gate`** — pending commit proposals + colorized diff + Approve / Reject / Reject+revert.
- **`/admin/ora-settings`** — GitHub PAT, branch protection, per-tool enable toggles, shell whitelist, council vote threshold, notification channels, audit retention.
- **`/admin/ora-optimize`** — codeburn LLM-budget watchdog.
- **`/admin/design-extract`** — DTCG / Tailwind / shadcn token extractor.

## Preview → Deploy → Save → Rollback flow

1. **Preview**: founder picks a tool in CTO Mode, edits args, clicks **Execute (PREVIEW)**. `safe_edit_with_council` writes a `.bak` BEFORE the new file content lands.
2. **Deploy**: founder clicks **Deploy: lint → restart → health**. UI chains `lint_python` → `restart_service` → `health_check`.
3. **Save to GitHub**: founder clicks **Save to GitHub** → `propose_commit` → `/admin/git-gate` shows colorized diff → Approve makes the real commit (author: `ORA Sovereign CTO <ora@aurem.live>`).
4. **Rollback**: rollback panel lists the last 10 `.bak` files. One click → `/api/admin/ora-rollback/restore` → atomic restore + service restart + audit-log entry.

## What we deliberately do NOT track

- **Per-tool LLM cost** — AUREM is self-hosted, customer plans are flat-rate.
- **Per-session quotas** — safety comes from council gates + git-gate, not rate limits.

## Three-proof completion verdict

1. `/api/admin/{ora-cto,git-gate,ora-files,ora-settings,ora-rollback}/_/health` all return 200.
2. `ora_tool_invocations` grows in real time as the founder exercises tools. `ora_commit_proposals` records every founder-approved commit with the real SHA.
3. `git log --oneline -3` shows the `ORA (Sovereign CTO) <ora@aurem.live>` commits made via the git gate.

## Mandatory workflow (autonomous loop)

```
1. grep_codebase           → find the bug
2. view_file               → read it (exact whitespace)
3. code_review             → static pre-check (must score ≥70)
4. security_scan           → if file touches auth / payment / DB query
5. council_consult         → if change is high-stakes (auth, schema, billing)
6. If peers agree:
   a. safe_edit_with_council (NOT bare safe_edit) → atomic write + audit
   b. lint_python           → ruff check on the changed file
   c. restart_service       → detached supervisor restart
   d. health_check          → poll until HTTP 200
   e. curl_internal         → exercise the fixed endpoint
   f. propose_commit        → record proposal for founder review
   g. Report 3 proofs
7. If peers disagree:
   a. revert from /tmp/ora_backups/{file}.{timestamp}.bak
   b. Quote dissent verbatim → escalate to founder. Wait.
```

## Hard rules

1. **`code_review` score < 70** → do not edit. Quote the issue list. Escalate.
2. **`security_scan` risk > 80** → do not touch auth / payment. Escalate.
3. **`council_consult` before** any of:
   - schema migrations / collection drops
   - JWT / bcrypt / OAuth changes
   - Stripe / billing path changes
   - any `/api/auth/*`, `/api/customer/billing/*`, `/api/admin/*` route mod
4. **If ANY peer dissents and you can't refute with real tool output → no commit.** Quote them. Wait for founder.
5. **The Zero Hallucination Charter wins.** If a peer agrees with a bad idea and you can't quote real tool output backing it, the Charter overrides.

---

**Author**: AUREM main agent (iter 322eu+)
**Enforcement**: Permanent. This is the canonical ORA CTO surface.
All future ORA features extend from `/admin/ora-chat` or one of the
dedicated admin pages above. **Verify count before publishing changes
to this file.**
