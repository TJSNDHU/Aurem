# AUREM Security Patterns Playbook (Skill: AUREM-SEC-PATTERNS-V1)
> **Audience**: ORA CTO + all 28 internal AUREM agents.
> **Mode**: When a code-review / autonomous-repair task is dispatched, scan candidate diffs against EVERY pattern below. If a match is found, propose the fix template through `safe_edit_with_council` (council-gated). Never apply directly to auth / payments / vault code without founder approval.

---

## Universal Workflow
1. **Reproduce-first**: never patch a pattern until you've proven the broken state via grep / curl / pytest.
2. **False-positive guard**: an LLM-pasted bug is real only when the actual file at the claimed line matches the claim. If the file or symbol doesn't exist → reject with proof.
3. **Token discipline**: one grep verifies many bugs in parallel; never re-read the same file twice in a session.
4. **Test contract**: every fix must ship with a pytest in `/app/backend/tests/test_round*_fixes.py` that grep-asserts the patched code.
5. **Council gate**: `safe_edit`, `shell_exec`, `propose_commit` always go through `*_with_council`. Direct dispatch is denied by `_PUBLIC_DENYLIST`.

---

## Pattern Library — 45 audited vulnerability classes

Format: `PAT-NN | name | detect_regex | fix_template | impact`

### ─── AUTHENTICATION & AUTHORIZATION ───

**PAT-01 | bare-decode admin gate**
- detect: `def\s+_?verify_admin[\s\S]{0,300}?return\s+payload` WITHOUT `is_admin` between
- fix: insert after `jwt.decode(...)`:
```python
from utils.admin_guard import is_admin_email
if not (payload.get("is_admin") or payload.get("is_super_admin")
        or payload.get("role") in ("admin","super_admin")
        or is_admin_email(payload.get("email"))):
    raise HTTPException(403, "Admin access required")
```
- impact: prevents every paying customer = admin (closes Bug 39/51/65).

**PAT-02 | empty-string JWT_SECRET fallback**
- detect: `JWT_SECRET",\s*""` OR `getenv\(['"]JWT_SECRET['"],\s*['"]['"]\)` OR `JWT_SECRET[^=\n]{0,80}or\s*['"]['"]`
- fix: `secret = os.environ.get("JWT_SECRET"); if not secret: raise HTTPException(500, "JWT not configured")`
- impact: missing env var no longer = "every forged token accepted" (Bug 61).

**PAT-03 | endpoint missing auth dependency**
- detect: a public-state-mutating route (`@router.(post|put|delete|patch)`) with NO `Depends(...require_admin|...require_auth)` AND no `Authorization` header check in body
- fix: add `dependencies=[Depends(_require_admin)]` to the decorator OR call `_require_auth(request)` first line.
- impact: prevents unauthenticated DB queries, mass blasts, file edits (Bug 40, 42, 48, 55, 56, 62, 63, 64, 66, 68, 69).

**PAT-04 | hardcoded credential default**
- detect: `os.environ.get\(['"][A-Z_]*(PASSWORD|KEY|SECRET|TOKEN)['"],\s*['"][^'"]{6,}['"]\)`
- fix: drop the default → `VAR = os.environ.get("X"); if not VAR: raise|disable_route(503)`
- impact: deletes leaked credentials (Bug 47, 49, 57, 70).

**PAT-05 | `email` claim grants admin**
- detect: `if.*or\s+payload\.get\(['"]email['"]\)`
- fix: drop the `email` shortcut entirely; use `is_admin_email(payload.get("email"))` instead.
- impact: closes Founders Console mass-escalation (Bug 65).

**PAT-06 | client-side JWT decode for routing**
- detect (JSX): `atob\(\s*[a-zA-Z_]+\.split\(['"]\.['"]\)\[1\]`
- fix: navigate based on server-returned `role`/`is_admin` field in the login response body, never re-decode client-side for security decisions.
- note: this is UX-only, not a server bug — but flag for code review.

---

### ─── INPUT VALIDATION ───

**PAT-07 | SSRF — user URL fetched without IP blocklist**
- detect: `httpx.AsyncClient[\s\S]{0,200}\.get\(.*\bbody\.url|.*request\.url|.*payload\["url"\]`
- fix: resolve hostname, reject `ip.is_private | is_loopback | is_link_local | is_multicast | is_reserved | is_unspecified`. See `routers/deep_scan_router.py::_is_private_or_loopback`.
- impact: blocks 169.254.169.254 AWS metadata, internal services (Bug 40).

**PAT-08 | open redirect**
- detect: `RedirectResponse\(.*(redirect_url|next|return_to|state_data\[)` where source comes from query/body
- fix: allowlist origin via `urlparse().scheme + "://" + .netloc` against an env-driven set. Reference: `routers/google_oauth_router.py::_safe_redirect`.
- impact: closes credential-leak via attacker-controlled redirect (Bug 41).

**PAT-09 | XSS via `document.write` / unescaped innerHTML**
- detect (JSX): `\.document\.write\(|innerHTML\s*=` with template literal containing `\${[^}]*(topic|title|name|message)}`
- fix: `_esc = s => String(s||'').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#x27;'}[c]))`; interpolate `_esc(value)`.
- impact: closes title-tag breakouts (Bug 50).

**PAT-10 | webhook signature short-circuit**
- detect: `if\s+(os\.environ\.get|signature_set)\s+\band\s+\bsig\b\s+and\s+not\s+_verify`
- fix: split — first reject missing sig if key configured, then reject invalid sig. No short-circuit with `and sig`.
- impact: closes fake webhook injection (Bug 58).

**PAT-11 | profile update accepts privileged fields**
- detect: `ProfileUpdate|UserUpdate` Pydantic model declares `email|role|is_admin|tenant_id|permissions` AND handler does `**update_fields` to Mongo update_one
- fix: remove privileged fields from the model AND defensive-pop in handler before update.
- impact: closes 2-API-call customer-to-admin path (Bug 46).

---

### ─── CRYPTO & SECRETS ───

**PAT-12 | password reset token stored plaintext**
- detect: `password_resets[\s\S]{0,200}\$set[\s\S]{0,80}"token":\s*[a-z_]+token`
- fix: `token_hash = hashlib.sha256(token.encode()).hexdigest()`; store `token_hash`, look up by hash. Backward-compat: `$or: [{token_hash}, {token}]` during migration.
- impact: DB leak no longer hands attacker usable tokens (Bug 11).

**PAT-13 | reset / verify token replayable**
- detect: token verification path that does NOT mark `used=True` or insert a JTI before allowing the mutation
- fix: persist `jti` to a TTL-indexed collection on first use; reject on second sighting. Reference: `bin_reset_token_jtis`.
- impact: closes intercept-replay (Bug 33).

**PAT-14 | encryption key default fallback**
- detect: `ENCRYPTION_KEY\s*=\s*os.environ.get\([^,]+,\s*['"][^'"]+['"]\)`
- fix: strict require; raise `HTTPException(500)` in the `_get_aes_key()` if missing.
- impact: prevents vault decrypt with public string (Bug 49).

**PAT-15 | `lru_cache` on key-rotating singleton**
- detect: `@lru_cache[\s\S]{0,80}def\s+(get_fernet|get_aes_key|get_cipher)`
- fix: replace with a re-readable getter that respects env-var rotation. Tag the cache with the key hash if memoization is needed.
- impact: ensures key rotation actually rotates (Bug 25 — pre-fixed but pattern stays in playbook).

---

### ─── EVENT-LOOP & PERFORMANCE ───

**PAT-16 | sync SDK in async route**
- detect: `async\s+def[\s\S]{0,400}(stripe\.[A-Z][a-zA-Z]+\.[a-z_]+\(|twilio.*messages\.create\(|sendgrid.*send\(|smtplib\.)\s*[^a]` (no preceding `await` and no `to_thread`/`run_in_executor`)
- fix:
```python
result = await asyncio.to_thread(sdk_call, arg1, arg2)
# or for partial:
result = await loop.run_in_executor(None, functools.partial(sdk_call, **kwargs))
```
- impact: prevents 300-2000ms event-loop stalls cascading into 524 (Bug 12, 43).

**PAT-17 | unbounded `defaultdict(list)` accumulator**
- detect: `defaultdict\(list\)|defaultdict\(int\)` in module scope without TTL/eviction
- fix: `from cachetools import TTLCache; failed_logins = TTLCache(maxsize=50_000, ttl=…)`
- impact: prevents RAM creep until OOM (Bug 18, 24).

**PAT-18 | non-atomic counter (TOCTOU)**
- detect: `attempts = .*\.get\("attempts",\s*0\)\s*\+\s*1[\s\S]{0,200}\.update_one`
- fix: Redis `INCR` (atomic) with `EXPIRE` on first increment; `asyncio.Lock()` fallback for in-memory mode.
- impact: closes brute-force halving (Bug 35).

**PAT-19 | `_safe_task` swallowing exceptions silently**
- detect: `async def _wrapper.*await\s+coro\b[\s\S]{0,300}except[\s\S]{0,200}logger\.(error|warning)\([^)]*\)\s*$` with no restart loop
- fix: convert to `while True: try: await factory() except: sleep + retry up to max_restarts`.
- impact: scheduled cron tasks actually restart instead of silently dying (Bug 13).

---

### ─── DATA EXPOSURE & TENANCY ───

**PAT-20 | unauthenticated PII endpoint keyed by guessable id**
- detect: `@router\.(get|post)\([^)]*\{[a-z_]+_id\}[^)]*\)\s*\nasync\s+def[\s\S]{0,400}(payment_transactions|customers|onboarding|orders)\.find_one` without auth check
- fix: require Bearer JWT, verify caller's email matches transaction's owner OR caller is admin.
- impact: closes guessable-ID PII leak (Bug 34).

**PAT-21 | `_id` in Mongo projection**
- detect: `find_one\((?!.*\{["_]id["]?:\s*0)|aggregate\([^)]*\)` returning to JSON without `{"_id": 0}`
- fix: always project `{"_id": 0}` OR use a Pydantic response_model.
- impact: prevents `ObjectId is not JSON serializable` 500s.

**PAT-22 | scoped DB falls through to raw on auth-miss**
- detect: `def\s+_resolve.*tenant_id\s*=\s*TenantGuard.get\(\)[\s\S]{0,100}if\s+not\s+tenant_id:\s*\n\s*return\s+raw`
- fix: log-then-deny — return a sentinel that 403s on any read. Reference: `scoped_db.py::_resolve` (Bug 37 backlog).
- impact: prevents cross-tenant collection access on unauthenticated routes.

**PAT-23 | `env` shell tool leaks new env vars**
- detect: `_redact_env|SENSITIVE\s*=\s*\(` list missing one of `URL, WEBHOOK, HASH, PASS, CREDENTIAL, AUTH, PRIVATE, SIGNATURE, API`
- fix: keep `SENSITIVE` aligned to that union OR switch to allow-list of safe vars.
- impact: prevents REDIS_URL / DATABASE_URL / ADMIN_PASSWORD_HASH leakage (Bug 31).

---

### ─── INFRA / CONFIG ───

**PAT-24 | `find_one`/`update_one` ignores `DuplicateKeyError`**
- detect: `await db\.[a-z_]+\.insert_one\(` inside register/signup/create path without try/except on `pymongo.errors.DuplicateKeyError`
- fix: wrap insert in try/except; translate to 400 with same message as the pre-check. Also ensure unique index exists.
- impact: closes register race-condition (Bug 17).

**PAT-25 | circular import via `import server`**
- detect: `import server as ` inside any module that's imported by `server.py`
- fix: `import sys; _srv = sys.modules.get("server"); _db = getattr(_srv, "db", None) if _srv else None`
- impact: avoids half-built module → silent None caches (Bug 26).

**PAT-26 | hardcoded founder email**
- detect: literal `teji.ss1986@gmail.com` (or any personal email) anywhere outside `/memory/` docs
- fix: `os.environ.get("FOUNDER_EMAIL") or "fallback@aurem.live"` (for tests only); production must set env.
- impact: removes PII from source (Bug 27).

**PAT-27 | JWT in URL query parameter**
- detect: `websocket\.query_params\.get\(['"]token['"]\)`
- fix: accept token as first message after `websocket.accept()` — never URL-embedded.
- impact: prevents token leak via access logs / browser history (Bug 52 — deferred but tracked).

**PAT-28 | rate-limit by `defaultdict` of timestamps without floor**
- detect: rate-limit windows that don't prune before checking — leads to false negatives + unbounded growth
- fix: prune-then-check inside a function backed by TTLCache.
- impact: tightens rate-limit semantics under sustained load (Bug 18 helper functions).

---

### ─── TOOL & DISPATCH SAFETY ───

**PAT-29 | dangerous tool in public registry**
- detect: a `TOOL_REGISTRY` entry whose `fn` is a raw file-editor or shell-exec primitive AND no council wrapper
- fix: register only the `*_with_council` wrapper; add the bare primitive to `_PUBLIC_DENYLIST` so `invoke_tool` rejects it.
- impact: closes RCE-via-admin-panel (Bug 30).

**PAT-30 | `.env` family not in write-forbidden list**
- detect: `_WRITE_FORBIDDEN_FILES` tuple missing any of `.env.txt, .env.staging, .env.development`
- fix: extend the tuple. Reference: `services/ora_tools.py:626`.
- impact: prevents `safe_edit` mutating secret files (Bug 36).

---

### ─── BIOMETRICS / EDGE AUTH ───

**PAT-31 | face/voice verify with no lockout**
- detect: `face_verify|voice_verify|face_distance` route without rate-limit query or `count_documents` recent-fail check
- fix: count failures in window from audit log, cap at 5/15min, reject with 429.
- impact: closes biometric brute-force (Bug 71).

**PAT-32 | accepts all-zero descriptor**
- detect: face verify path that doesn't validate `all(abs(v) < 1e-9)` on input or stored avg
- fix: reject with 400; force re-enrollment if stored data is degenerate.
- impact: closes biometric match-on-zero trick (Bug 71).

---

## Detection Workflow (ORA-CTO drive cycle)

```
1. CRAWL  — diff scan against PAT-01..32 regex set.
2. CONFIRM — for each match, fetch the surrounding 30 lines + run a curl/pytest reproducer.
3. PROPOSE — generate the patch as `safe_edit_with_council` body; include the matched PAT-NN id.
4. GATE   — submit to council. Wait for founder approval (Telegram inline-button).
5. APPLY  — on approval, the council wrapper runs `safe_edit`; on reject, log + abort.
6. TEST   — auto-run the matching pytest from /app/backend/tests/test_round*_fixes.py.
7. COMMIT — propose_commit with PAT-NN in the message body. Never auto-push.
```

## False-Positive Self-Check (must run BEFORE proposing)
- File at claimed path exists? `os.path.exists(path)` → if False, REJECT.
- Symbol claimed by the audit actually present? `grep -c "symbol" path` → if 0, REJECT.
- Already-fixed marker? `grep -c "Bug-fix #NN" path` → if ≥1, REJECT (already patched).

## Hard Refusals (never patch without explicit founder go-ahead)
- Anything in `/app/backend/.env*` — read-only.
- `services/legion_queue_router.py` enqueue handler — the daemon executes shell on the founder's laptop.
- `routers/founders_console_router.py::self_edit_apply` — meta-edits to the editor itself.
- Migration scripts that touch `users.password_hash` of a real customer.
