# AUREM DEV SKILL: ora-tools-usage (P1 — read-only investigation hands)

## Status
**LIVE as of iter 322ej**. You have 9 real tools you can invoke right now via the admin-gated endpoint `POST /api/ora-tools/execute` with body `{"tool": "<name>", "args": {...}}`. All read-only. All audit-logged to `ora_tool_invocations`.

When the founder asks you to investigate, scan, count, or read — USE these tools. Don't recite from memory.

---

## The 9 Tools (verified working iter 322ej)

| Tool | What it does | Hard caps | Typical use |
|---|---|---|---|
| `grep_codebase` | Real `grep -rn` over `/app/backend` or `/app/frontend` | 12s, 200 results | "Where is function X defined?" |
| `view_file` | Read a file, range-clipped | 500 lines, 2MB file cap | "Show me the first 50 lines of server.py" |
| `view_dir` | List directory entries | 60 entries | "What's in /app/backend/services?" |
| `curl_internal` | GET our own `/api/*` (localhost only) | 8s | "What does /api/customer/audit/admin/live return?" |
| `db_count` | Mongo `count_documents` | 5s, allowlisted collections only | "How many active audits?" |
| `db_distinct` | Mongo `distinct(field)` | 8s, 200 values | "Which BINs have pixels firing?" |
| `git_log` | Recent commits on /app | 5s, max 30 | "What's deployed?" |
| `health_check` | Probe `/api/platform/health` | 8s | "Is backend up?" |
| `lint_python` | `ruff check` on a .py file (read-only) | 12s | "Does this file have syntax errors?" |

## Allowlists (security)

### Path allowlist (for grep, view, lint)
```
/app/backend, /app/frontend, /app/memory, /app/ora_skills, /app/scripts
```
Anything else returns `{ok: false, error: "path not allowed: ..."}`. Never bypass.

### DB collection allowlist (for db_count, db_distinct)
Prefixes allowed: `ora_*`, `agent_*`, `customer_*`, `campaign_*`, `pixel_*`, `audit_*`, `platform_users`, `users`, `leads`, `scan_*`, `deploy_*`, `pillar_*`, `sentinel_*`, `memoir_*`, `bin_*`, `intelligence_*`, `antigravity_*`, `skills_*`, `trial_*`, `stripe_*`, `client_*`, `system_*`, `heartbeats*`, `alerts`.

If a request needs a different collection, ask the founder to add it to `_ALLOWED_DB_PREFIXES` in `services/ora_tools.py`. Don't try workarounds.

### Forbidden patterns (blocked even inside allowed roots)
`/.env`, `/.ssh`, `/.git/config`, `node_modules` — all blocked. These exist for security; never request around them.

### Operator allowlist (for db filters)
`$where`, `$function`, `$accumulator` — BLOCKED. These allow arbitrary code execution. Use normal operators only.

---

## How to invoke (HTTP)

```bash
# List available tools (admin-gated)
curl -X GET https://aurem.live/api/ora-tools/list \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Execute a tool
curl -X POST https://aurem.live/api/ora-tools/execute \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tool": "grep_codebase", "args": {"pattern": "call_llm_with_meta", "file_glob": "*.py"}}'

# Audit log (last N invocations)
curl -X GET "https://aurem.live/api/ora-tools/invocations?limit=30" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Every response shape:
```json
{
  "ok": true,
  "tool": "grep_codebase",
  "elapsed_ms": 26,
  "ts": "2026-05-12T04:21:32+00:00",
  ...tool-specific fields...
}
```

On failure:
```json
{
  "ok": false,
  "error": "<exact error string>",
  "tool": "...",
  "elapsed_ms": 0,
  "ts": "..."
}
```

---

## Investigation patterns (use these — they work)

### Pattern A — Find code by concept
```
grep_codebase(pattern="async def call_llm", file_glob="*.py", root="/app/backend")
→ view_file(path=<top result>, max_lines=80)
→ propose change
```

### Pattern B — Verify endpoint health
```
health_check()
→ curl_internal(endpoint="/api/customer/audit/admin/live")
→ quote http_status + body verbatim
```

### Pattern C — DB drift check
```
db_count(collection="customer_audits", filter_={"status": "completed"})
→ db_distinct(collection="pixel_events", field="bin_id")
→ report counts + distinct BINs
```

### Pattern D — "What's deployed" answer
```
git_log(n=5)
→ paste commits verbatim
```

### Pattern E — Bug repro
```
grep_codebase(pattern="<error message>", file_glob="*.py")
→ view_file(path=<match>, max_lines=120, start=<line - 60>)
→ identify the failing branch
→ propose smallest patch (BEFORE/AFTER blocks)
```

---

## What you CANNOT do yet (P1 limits)

| Capability | Status | When |
|---|---|---|
| Write/edit files | ❌ NOT in P1 | P3 build (founder must trigger) |
| Run `pytest` | ❌ NOT in P1 | P2 build |
| Restart services | ❌ NOT in P1 | P3 build with approval gate |
| `git commit/push` | ❌ NOT in P1 | P3 build (approval-gated) |
| Call subagents (integration / troubleshoot / testing) | ❌ NOT in P1 | P4 build |
| External HTTP (`curl google.com`) | ❌ Hard block | P5 build with allowlist |
| Read `.env` / secrets | ❌ Hard block | NEVER (security) |

When a request needs one of these, state clearly: "P1 doesn't have <capability>. Main agent must execute, or founder must approve P<N> build."

---

## Audit trail

Every invocation lands in `ora_tool_invocations` with shape:
```
{ts, actor, tool, args, ok, error?, elapsed_ms}
```

You can query your own history:
```
curl /api/ora-tools/invocations?limit=30&tool=db_count
```

Use this to:
- Show the founder you actually did work (real proofs)
- Detect your own loops ("I called grep_codebase 5 times with the same args — that's hallucination behavior")
- Reproduce a chain of investigation

---

**Bottom line**: You finally have hands. Use them every time. Never claim a number you didn't tool-fetch.
