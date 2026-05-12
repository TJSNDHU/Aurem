# AUREM — ORA Mistakes & Self-Correction (iter 322ey lessons)

> **You ARE the agent who made these mistakes.** Read this before designing
> any new file. Each lesson maps to a real bug caught by the supervisor in
> iter 322ey. If you find yourself about to repeat one, STOP and re-route.

---

## 1. NEVER embed literal triple-backticks inside an f-string

### What happened (iter 322ew)
You designed `aurem-cto/api/services/orchestrator.py` with:
```python
_TOOL_HELP = (
    f"Emit a tool_call fenced with ```tool_call like this..."
)
```
The first ` ``` ` you typed terminated your OWN output mid-file at line 41
— a 90-line orchestrator was truncated to 41 lines. Founder had to
manually rewrite.

### Lesson — DO THIS INSTEAD
Assemble fences at runtime so neither your code-gen output NOR the file's
docstring gets accidentally terminated:
```python
_BT = chr(96) * 3  # "```"
_TOOL_HELP = f"Emit a tool_call fenced with {_BT}tool_call like this..."
```

### Self-check rule
Before emitting any file containing the substring "```" or backtick syntax
inside an f-string / multi-line string, mentally replace it with
`chr(96) * 3` or `\u0060\u0060\u0060`.

---

## 2. AUREM users are keyed by `email`, NOT by `_id` or `sub`

### What happened (iter 322ey)
In `founder_saves_router.py:get_admin_user` you wrote:
```python
payload = jwt.decode(token, secret, algorithms=["HS256"])
user_id = payload.get("sub")
user = await _db.users.find_one({"_id": user_id})  # WRONG
```
Users collection uses `email` as the lookup key. The `_id` field stores
a string like `plat_efdd1c6a5d703d7c7736de3f`, not the JWT's `sub`.

### Lesson — DO THIS INSTEAD
```python
email = (payload.get("email") or payload.get("sub") or "").lower()
# Trust JWT's is_admin claim if present (login already verified):
if payload.get("is_admin") or payload.get("is_super_admin"):
    return {"email": email, "is_admin": True}
user = await _db.users.find_one({"email": email}, {"_id": 0})
```

### Self-check rule
Whenever you write `_db.users.find_one(...)`, the filter MUST be on
`email`. Never `_id`, never `sub`, never `user_id`.

---

## 3. Audit timestamps are stored as ISO STRINGS, not datetime objects

### What happened (iter 322ey)
You wrote:
```python
cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
count = await _db.ora_tool_invocations.count_documents(
    {"ts": {"$gte": cutoff}}   # WRONG — ts is a string
)  # returns 0 EVERY time
```
The collections `ora_tool_invocations`, `ora_governance_overrides`,
`ora_commit_proposals` all store `ts` and `decided_at` as
`datetime.now(timezone.utc).isoformat()` strings. MongoDB compares
datetime vs string as different BSON types → no matches.

### Lesson — DO THIS INSTEAD
```python
cutoff_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
count = await _db.ora_tool_invocations.count_documents(
    {"ts": {"$gte": cutoff_iso}}   # works: lexicographic ISO compare
)
```
And NEVER call `.isoformat()` on a value that's already a string:
```python
last_save_ts = doc.get("decided_at")  # already a string
# WRONG: last_save_ts.isoformat()   ← AttributeError
return {"last_save_ts": last_save_ts}  # pass through verbatim
```

### Self-check rule
Audit collections (`ora_*`, `*_proposals`, `*_overrides`) → timestamps
are ALWAYS ISO strings. Use `.isoformat()` when writing the filter, not
when reading the result.

---

## 4. Frontend ⇄ backend wire shapes MUST match — verify field names

### What happened (iter 322ew)
You designed `aurem-cto/ui/src/App.jsx` with:
```jsx
axios.post("/api/chat", { message: input })
const oraMsg = { content: res.data.response, iters: res.data.iters }
```
But `main.py` expects `{prompt, max_tool_iters}` and returns
`{content, iterations}`. All 4 field names were wrong. The chat UI
silently returned undefined.

### Lesson — DO THIS INSTEAD
When you design BOTH the React caller AND the FastAPI handler, write
them in the SAME design batch and use the EXACT field names from your
Pydantic request/response models. Quote the model verbatim in the JSX:
```jsx
// ChatRequest(prompt: str, max_tool_iters: int = 4)
// ChatResponse(ok, content, provider, iterations)
const res = await axios.post(API + "/api/chat", {
  prompt: input, max_tool_iters: 4
})
const oraMsg = { content: res.data.content, iters: res.data.iterations }
```

### Self-check rule
Before emitting a JSX `axios.post` / `fetch` call, list the EXACT JSON
keys you're sending and reading. Cross-reference against the Pydantic
model in the same design batch.

---

## 5. SQLite schemas MUST include every column the writer uses

### What happened (iter 322ew/ey)
`aurem-cto/api/main.py` created `outbox_pending` with columns
`(id, created_at, status, payload, error)`. But the worker
(`outbox/worker.py`) writes to `retry_count` and `processed_at`. First
worker pass crashed.

### Lesson — DO THIS INSTEAD
When you design a schema, immediately grep the consumer code for every
`UPDATE`, `INSERT`, `SELECT` against that table and verify each
referenced column exists in the CREATE TABLE. Producer ↔ consumer
schema parity is non-negotiable.

### Self-check rule
Anytime you write `CREATE TABLE`, the columns set must be a SUPERSET
of every column name referenced anywhere else in the project.

---

## 6. When a tool fails, REPORT the failure — never invent the result

### What happened (iter 322ew Round 1 Council Gate)
`view_file('/app/aurem-cto/api/main.py')` rejected (allowlist missed
the dir). Instead of saying "I couldn't read the file", you proceeded
to do a `peer_review` with NO source code and invented 3 P0 issues
(stack trace leakage, missing AuthMiddleware) referencing code that
didn't exist. Founder caught the hallucination.

### Lesson — DO THIS INSTEAD
If ANY tool call returns `ok: false` or empty result, your next move is
a one-line status report:
> "I couldn't read /app/aurem-cto/api/main.py — view_file returned
> `path not in allowlist`. Can the founder extend `_ALLOWED_ROOTS`?
> I'll wait."
DO NOT proceed with downstream work that assumed the failed step
succeeded.

### Self-check rule
Anti-hallucination: every `peer_review`, `code_review`, `propose_commit`
that depends on file contents MUST have a SUCCESSFUL `view_file` /
`grep_codebase` in the same tool_invocations list, or you abort.

---

## Meta-rule

When the supervisor catches a bug and patches it for you, READ the diff.
The fix is your future self speaking. Encode the pattern in this file (or
adjacent skill docs) so the next ORA instance never repeats it.
