# AUREM DEV SKILL: ora-write-and-restart (P3 — Surgical Writer + Service Supervisor)

## Status
**LIVE as of iter 322en.** ORA can now WRITE files and RESTART services. Real edits. Real signals to the kernel. No mocks. Every action audited.

This is the bridge from "investigation" to "production work." With the previous P1+P2 (read-only tools + shell_exec), ORA could only LOOK at the system. With P3 it can finally CHANGE it — but only inside tight, surgical guardrails.

---

## TWO NEW TOOLS

### 1. `safe_edit` — Atomic File Writer

**WHAT**: exact-match find/replace. No overwrites. No guessing.

```json
POST /api/ora-tools/execute
{
  "tool": "safe_edit",
  "args": {
    "path": "/app/backend/services/foo.py",
    "find_string": "MAX_RETRIES = 3",
    "replace_string": "MAX_RETRIES = 5",
    "expected_occurrences": 1
  }
}
```

Response on success:
```json
{
  "ok": true,
  "occurrences_replaced": 1,
  "backup_path": "/tmp/ora_backups/20260512_044918__app__backend__services__foo.py.bak",
  "bytes_before": 1240,
  "bytes_after": 1240,
  "diff_preview": "diff --git ... -MAX_RETRIES = 3\n+MAX_RETRIES = 5",
  "revert_cmd": "cp /tmp/ora_backups/... /app/backend/services/foo.py"
}
```

#### Write-allowed roots
```
/app/backend
/app/frontend/src
/app/memory
/app/ora_skills
/app/scripts
```
Anything outside → `{"ok": false, "error": "path not allowed"}`.

#### Hard-blocked files
`.env`, `.env.local`, `.env.production`, `requirements.txt`, `package.json`, `package-lock.json`, `yarn.lock`, anything in `/.git/`, `/node_modules/`, `/__pycache__/`, `/migrations/`, `/.next/`, `/build/`, `/dist/`.

#### Refusal triggers (the safety rails)
| Condition | Result |
|---|---|
| Path outside allowlist | `path not allowed: ...` |
| File doesn't exist | `file does not exist` |
| File >2 MB | `file too large for safe edit` |
| `find_string` empty | `find_string required (non-empty)` |
| `find_string` not in file | `occurs 0×; expected 1. Refusing to guess` |
| `find_string` appears more times than `expected_occurrences` | `occurs N×; expected M` |
| `find_string == replace_string` | `no-op edit refused` |
| `replace_string` >200 KB | `too large` |

#### Backup discipline
Every successful edit auto-creates `/tmp/ora_backups/<UTC-timestamp>__<safe-path>.bak` with the ORIGINAL content. Revert with the `revert_cmd` field from the response.

#### Atomic write
Writes go to `<file>.ora_tmp` first, `fsync()`, then `os.replace()`. No partial-write corruption possible.

---

### 2. `restart_service` — Service Supervisor

**WHAT**: real `supervisorctl restart <service>` — detached so the caller gets an ack BEFORE the backend dies.

```json
POST /api/ora-tools/execute
{"tool": "restart_service", "args": {"service": "backend"}}
```

Response (returns instantly — restart fires 1.5s later in detached process):
```json
{
  "ok": true,
  "service": "backend",
  "scheduled_at": "2026-05-12T04:51:17",
  "scheduled_via": "detached_setsid",
  "delay_seconds": 1.5,
  "log_path": "/tmp/ora_restart_backend.log",
  "note": "Restart of 'backend' scheduled to fire 1.5s after this response. Poll /api/platform/health to verify recovery."
}
```

#### Restart whitelist (hard-coded)
- `backend`
- `frontend`

Everything else (`mongo`, `mongodb`, `postgres`, `redis`, `nginx`, `aurem-watchdog`, OS services) → `{"ok": false, "error": "service not in restart whitelist"}`.

#### Why the 1.5s detach?
When you call `supervisorctl restart backend` from INSIDE the backend, supervisor sends SIGTERM to backend → backend dies → in-flight HTTP response never lands → caller sees a connection reset. The detached `setsid nohup` ensures the restart fires AFTER the response flushes back.

#### Recovery verification (you MUST do this)
After triggering a restart, the caller polls `/api/platform/health` until HTTP 200 returns. Typical recovery window: 10-15 seconds.

---

## THE AUTONOMOUS FEEDBACK LOOP (the whole point)

Now that you have read + write + restart + verify, you can run the full self-correcting cycle:

```
1. grep_codebase   → find the bug
2. view_file       → read the relevant lines
3. safe_edit       → patch it (with exact find/replace)
4. lint_python     → verify syntax (ruff)
5. shell_exec git diff → confirm what changed
6. restart_service backend → reload code
7. health_check    → confirm service is back
8. curl_internal   → exercise the fixed endpoint
9. If success: report
   If fail:   cp <backup_path> <file> + retry
```

This IS the loop. Run it. Never claim "fixed" without running steps 4-7 successfully.

---

## NEGATIVE TESTS (verified iter 322en — all rejected)

| Attack | Result |
|---|---|
| `safe_edit` on `/app/backend/.env` | BLOCKED `forbidden pattern: '/.env'` |
| `safe_edit` with non-existent `find_string` | REFUSED `occurs 0×; expected 1` |
| `safe_edit` with ambiguous `find_string` (appears 2× when expected=1) | REFUSED `occurs 2×; expected 1` |
| `restart_service mongo` | BLOCKED `service not in restart whitelist: mongo` |
| `restart_service postgres` | BLOCKED `not in whitelist` |
| `safe_edit` with `find_string == replace_string` | REFUSED `no-op edit refused` |

---

## RULES YOU MUST FOLLOW (Charter still wins)

1. **NEVER call `safe_edit` without first running `view_file`** to get the exact whitespace. Cargo-culted edits fail.
2. **NEVER skip the backup verify** — `backup_path` in the response is your undo button. Quote it in your status update.
3. **NEVER restart a service without a reason** — every restart wakes founder's monitoring. Restart only after a safe_edit, and only if it touches loaded modules.
4. **ALWAYS poll health AFTER a restart** — `health_check()` until HTTP 200. Do NOT claim success until you've seen 200.
5. **NEVER edit `.env`, package.json, requirements.txt** — these need founder approval + a deploy. Tell the founder.
6. **NEVER use safe_edit to insert "new features"** — P3 is for SURGICAL fixes, not greenfield code. Greenfield = founder's job.
7. **If lint fails after safe_edit**, immediately revert with the `revert_cmd` and report to founder.

---

## Iter index addition

| Iter | Lesson |
|---|---|
| 322ej | P1 — 9 read-only tools |
| 322ek | Zero Hallucination Charter (THE LAW) |
| 322el | Tool-call loop in llm_gateway |
| 322em | P2 — Python Subprocess Bridge (kernel-level execution) |
| 322en | **THIS SKILL — P3 Surgical Writer + Service Supervisor** (autonomous feedback loop unlocked) |

---

**Bottom line**: You now have hands AND can move them. The kernel obeys you. Use this power surgically. Every edit is logged, backed up, and revertible. Every restart is scheduled. The founder is watching the audit log.

Don't break production. Don't bypass the rails. Don't claim success without the 3 proofs.
