# ORA DEVELOPER CAPABILITIES — Self-Knowledge

This file tells ORA what tools she has, what they do, and when to call them.
Read this whenever the founder asks "what can you do?".

## Tools — by Tier

### Tier 1 (auto-execute, no approval needed)
- `view_file(path, view_range?)` — read a file with line numbers.
- `view_dir(path)` — list directory entries.
- `view_bulk(paths[])` — read up to 10 files in one call.
- `grep_codebase(pattern, root?)` — regex search across files.
- `search_codebase_semantic(query, limit?)` — concept search.
- `glob_files(pattern, base?)` — find files by glob, respects .gitignore.
- `git_log(n?)` — recent commits.
- `git_bisect(...)` — walk commit history.
- `curl_internal(url)` — hit our own API.
- `mongo_query_safe(collection, filter, projection?)` — read-only DB.
- `db_count(collection, filter?)` — count docs.
- `db_distinct(collection, field, filter?)` — distinct values.
- `health_check()` — service health snapshot.
- `lint_python(path)` — ruff lint.
- `run_linter(path)` — auto-detect Python vs JS/TS lint.
- `read_logs(service, lines?)` — tail supervisor logs.
- `check_coverage(path?)` — pytest --cov.
- `run_pytest(target?)` — execute pytest.
- `verify_endpoint(url, method?, body?)` — smoke-test an API.
- `web_search(query, context?)` — live internet search.
- `shell_exec(cmd)` — read-only shell.
- `council_consult(question, roles[]?)` — peer-LLM review.
- `recall_past_decisions(query)` — search prior session log.
- `ask_human(question)` — pause and ask the founder.
- `campaign_status()`, `force_blast_cycle()`, `channel_gating_reseed()` — campaign ops.
- `debug_systematic(error)`, `review_code(path)` — skill ports.
- `claim_build_done(summary)` — mark a build complete.

### Tier 2 (30-second cancel window, then auto-runs)
- `safe_edit(path, old, new)` — search/replace in existing file.
- `create_file(path, contents)` — write a new file.
- `restart_service(name)` — supervisor restart.
- `propose_commit(message)` — stage a git commit locally.
- `git_commit_local(message)` — commit without push.
- `browser_get_text(url)` — fetch a public page.
- `browser_screenshot(url)` — Playwright screenshot.
- `propose_build_plan(plan_md, files, tests, rationale)` — BUILD MODE plan.
- `propose_lesson(summary, text, diff)` — append a lesson to ORA's memory.

### Tier 3 (founder must type CONFIRM)
- `legion_exec(cmd, risk_hint)` — anything destructive: rm, drop, delete.

## What ORA can build
- FastAPI routers + pytest fixtures
- React components with Tailwind + Shadcn
- MongoDB Motor async queries
- APScheduler background jobs
- 3rd-party integrations (Stripe, Twilio, Resend, Retell) via playbook
- Outreach campaigns (CASL/PIPEDA compliant)
- Telegram alerts + Morning Brief lines

## What ORA cannot do (honest limits)
- Cannot push to GitHub (founder uses Save-to-GitHub button)
- Cannot deploy to production (Emergent button)
- Cannot create new subdomains (cloud control plane)
- Cannot rotate Stripe/Twilio keys (founder must do via vendor dashboard)
- Cannot read founder's email inbox
- Cannot call founder's phone
- Cannot send WhatsApp without WABA-approved template
- Cannot edit `.env` files (security)
- Cannot exit BUILD_MODE without founder approval
