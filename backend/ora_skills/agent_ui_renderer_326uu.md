# ORA-CTO UI Skills (iter 326uu) — Rich Result Rendering

> Founder mandate (2026-05): Bring ORA-CTO's chat UI to Emergent E1 parity.
> When you (ORA) propose / execute tools, the UI now has a 2-pane layout
> with a smart, tool-aware renderer for every result. You don't need to
> change behaviour — but you SHOULD know how your output is rendered so
> you can make outputs more readable for the founder.

## What the UI now does automatically

The frontend file `OraChatViews.jsx` defines a `SmartToolResult`
dispatcher. It inspects the tool name + the result dict shape and
picks the right viewer:

| Your tool result shape                              | Renderer            | What the founder sees                       |
|------------------------------------------------------|---------------------|---------------------------------------------|
| `safe_edit*` + `find_string` + `replace_string`     | **DiffView**        | Red `-` lines + green `+` lines             |
| `shell_exec*` stdout matches `\d+ passed`           | **TestResultBlock** | "✓ N passing in Xs" + collapsible body      |
| `shell_exec*` other                                 | **ShellOutputBlock**| stdout/stderr in two collapsibles, exit code|
| `view_file*` / `view_bulk`                          | **FileContentBlock**| File header + expandable content            |
| `lint_*`                                            | **LintBlock**       | Issue list with line + rule                 |
| `council_consult` / `peer_review`                   | **CouncilBlock**    | Each peer collapsible by role               |
| `ok: False` + `error: ...`                          | **ErrorContext**    | Error + likely cause + suggested fix        |
| Anything else                                       | **GenericJsonBlock**| Truncated preview + click-to-expand JSON    |

Additionally, the right-side **PreviewPane** mirrors the latest result
so it stays in view as the founder scrolls the chat.

## How to make your outputs render best

### 1. Keep `error` strings short and pattern-friendly
`inferErrorHint(err)` matches a small set of phrases to surface a
"likely cause + fix" hint to the founder. Stick to existing wording:

  - `path not allowed: ...`
  - `bad args for X: ...`
  - `unknown tool: ...`
  - `no valid roles after filter`
  - `not found, already processed, or expired`
  - `timeout` / `timed out`
  - `HTTP 5xx` / `rate limit` / `429`
  - `dissent` / `rejected by`
  - `creds_missing` / `api_key`

Don't invent new error vocabularies — extend `inferErrorHint` in
`OraChatViews.jsx` instead.

### 2. Numbered plans get auto-rendered as checklists
If your FIRST assistant message uses `1. step ...`, `2) step ...`, or
`- step ...` format with 2+ items, the UI extracts it via
`extractPlanSteps()` and renders a checklist above the chat. Items
strike through as tool_results accumulate.

**Good plan format:**
```
I'll do these steps:
1. Read the affected file
2. Write the fix
3. Run pytest to verify
```

**Bad plan format (no extraction):**
```
First I'll do this, then that, then the other thing.
```

### 3. For safe_edit, ALWAYS include `path` in the result
DiffView reads `result.path` (or `result.file_path`) for the header
link. If you omit the path the founder sees "(unknown file)".

### 4. For shell_exec with pytest, let the full summary line through
Don't truncate pytest output before the `=== X passed, Y failed in Zs ===`
line. The parser needs that line to compute the green/red header.

### 5. council_consult always returns the schema-correct opinions[]
Each opinion must have `role`, `ok`, `opinion`, optional `provider`.
The CouncilBlock renders one collapsible per peer.

## Halt-cause map (carry-over from iter 326qq → 326tt)

You can NO LONGER halt on:
  - Invalid council role slugs (falls back to default trio + note)
  - Wrong-arg-shape tool calls (returns args_spec for self-correction)
  - 150s wall-clock (now 300s default, env-overridable)
  - Transient 5xx / timeouts / rate limits (separate 5-strike bucket)
  - Approval-card "expired" race (UI now lifts the lock cleanly,
    asks for a fresh action)

If the loop halts now, it is one of:
  - 2 consecutive DETERMINISTIC failures (LLM brain mistake — fix and retry)
  - 5 consecutive TRANSIENT failures (env genuinely broken — escalate)
  - Wall-clock at 300s (founder asked for too much in one turn)

## File map

- `/app/frontend/src/platform/admin/OraChatViews.jsx` — all 12+ renderers
- `/app/frontend/src/platform/admin/OraChat.jsx`     — wires them in
- `/app/backend/services/ora_agent.py`               — emits expires_at, structured error_codes
- `/app/backend/services/ora_tools.py`               — dispatcher returns args_spec on bad-args
- `/app/backend/tests/test_iter326uu_*.py`           — 20 regression tests
