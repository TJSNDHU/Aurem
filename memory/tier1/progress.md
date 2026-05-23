# ORA SESSION PROGRESS — Live State

ORA writes here after every major step. ORA reads at session start.

## Format
```
---
Task: short task description
Succeeded: what worked this step
Blocker: what is stuck (or "none")
Next: exact next concrete action
Cost: $X.XX USD so far this session
Branch: current git branch
PIDs: [list of tracked background process IDs]
Updated: 2026-MM-DDTHH:MM:SSZ
---
```

## Current State

---
Task: iter 331c — Sprint 6 COMPLETE (metrics + consent network + Vanguard + portability audit)
Succeeded:
  - Sprint 6.1: Consent-Based Data Network. set_consent / get_consent state machine, anonymizer with PII regex defense-in-depth, record_network_event_if_consented hook in outreach pipeline, 30-day purge cron, /api/me/consent endpoints. CRITICAL compliance proof: data NEVER written if consent=false (verified by 2 dedicated unit tests).
  - Sprint 6.2: ora_session_metrics collection + health_snapshot + /api/admin/ora/health endpoint. Recommend_fork nudge fires when session crosses 100 tool calls.
  - Sprint 6.3: OraHealthTile cockpit component (reads health + Vanguard score). vanguard_alerts module sends Telegram if score <80, daily 03:45 UTC cron. Morning Brief now includes one-line security status. Frontend portability audit: 3 hardcoded API endpoints fixed (PublicStatus, useAuth, LuxeV2Pages); REACT_APP_PUBLIC_BASE_URL added as optional env var.
  - 124/124 regression tests passing. 14 new Sprint 6 tests. Real E2E: consent toggle round-trip + 30-day purge scheduling verified live against preview backend.
Blocker: none
Next:
  - User pushes to GitHub → redeploys aurem.live to ship Sprint 6.
  - Backlog: real vector embeddings (90 MB MiniLM-L6 + sqlite-vec) when memory grows past ~50 docs.
  - Backlog: aggregate predictive lead scorer that consumes aurem_network_leads (once enough consented tenants contribute).
Cost: $0.00 (all unit + curl tests; no LLM calls this sprint)
Branch: main
PIDs: []
Updated: 2026-02-23T22:00:00Z
---


---
Task: iter 331d — Developer Portal Foundation (Option A wrap-up + Day-0 welcome email)
Succeeded:
  - Most of Option A backend was already live from a previous segment (developer_portal_core.py with full state machine, developer_portal_router.py with 10 endpoints, invoke_tool token-wall + deduction hooks, ConsentToggleCard.jsx). This iter closes the remaining 3 deliverables.
  - Day-0 welcome email wired into verify_otp success path via fire-and-forget asyncio task. Subject "Welcome to ORA CTO — Your 1000 tokens are ready", branded HTML body with 3 getting-started steps (login → connect GitHub → tell ORA what to build), token cost table, BYOK callout. Uses existing services.email_service_resend wrapper (no new dependency). Replaced the old broken `from services.email_service import send_email` fallback (that module never existed — every previous OTP email silently failed to send and only logged).
  - Sandbox cleanup cron registered in routers/registry.py: APScheduler CronTrigger at 04:30 UTC daily, calls developer_portal_core.cleanup_inactive_sandboxes() which walks /tmp/ora-sandbox-* and removes folders untouched > ORA_SANDBOX_INACTIVE_DAYS (default 45).
  - Real bug found and fixed during testing: verify_otp() crashed with `can't compare offset-naive and offset-aware datetimes` when Mongo returned a tz-naive expires_at. Now normalizes any tz-naive Mongo datetime to UTC before comparison. Would have broken OTP verify in production once the first OTP roundtripped through Mongo.
  - New regression suite test_iter331d_developer_portal_foundation.py: 20 base cases expanding to 37 with parametrization. Covers signup state machine (anti-bot, disposable email reject), OTP issue + verify + expiry + lockout, JWT roundtrip, BYOK encrypt/decrypt, token deduction + token wall + cost table, 5 abuse patterns, rate limits (per-min + paid-tier bypass), 10 pixel domain edge cases, referral bonus, sandbox cleanup with tmp_path + monkeypatch, welcome email subject/body assertions, welcome email sends via Resend wrapper (monkeypatched), and end-to-end verify_otp → welcome-email fire-and-forget.
  - Full active regression: 355 / 359 green across iter 327d → 331d (4 pre-existing failures in test_iter327n + test_iter329 are stale assertions against pre-Sprint-1 _TIER1_FILES API — known issue carried over from iter 330f notes, not caused by this iter).
Blocker: none
Next:
  - User pushes to GitHub → redeploys aurem.live so iter 331d ships.
  - P1: Developer Portal frontend pages (/developers/signup, /connect, /dashboard, /analytics, /tokens, /terms, /settings).
  - P1: Rest of onboarding email sequence (Day 3, Day 7, Day 25) via APScheduler walking developer_accounts.
  - P2: Stripe integration for Starter ($9) / Builder ($39) / Pro ($99) token packages.
  - Pre-existing: 4 stale tier-1 memory loader tests need to be rewritten against the new folder-driven loader (not done — separate task).
Cost: $0.00 USD (pytest + lint only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-23T23:30:00Z
---

---
Task: iter 331e Batch A — Security hardening + email sequence + stale test repair
Succeeded:
  Part 1 — Security guards (new services/dev_security_guards.py):
    - SSRF guard `assert_url_safe`: blocks 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1, and exact-host list (localhost, kubernetes.default, metadata.google.internal, 169.254.169.254 AWS metadata, host.docker.internal, *.local, *.internal, *.intranet, *.lan, *.corp). Re-resolves hostnames via DNS and re-checks each returned IP — defeats DNS-rebinding (127-0-0-1.nip.io attacks). Fails closed on DNS failure.
    - File size limits `enforce_file_size_limits`: per-file 10 MB hard cap, per-session 50 MB cumulative cap, HTTP 413 envelope with plain-English message. Session totals tracked in-process dict; `reset_session_bytes` exposed for session release.
    - Concurrent session limit `acquire_session` / `release_session`: max 2 active per developer (env: ORA_DEV_MAX_ACTIVE_SESSIONS), tracked in `developer_accounts.active_sessions[]`. Stale sessions (heartbeat > 30 min) auto-pruned before counting. Same `session_id` twice = heartbeat refresh, not refusal.
    - Output masking `mask_sensitive_output`: walks nested dict/list and strips JWTs, bearer tokens, sk-*, sk_live_*, sk_test_*, pk_live_*, AIza*, re_*, mongodb:// URLs, telegram bot tokens, BEGIN PRIVATE KEY blocks, every env-var value whose name matches KEY|TOKEN|SECRET|PASSWORD|PASS|DSN|CONN_STRING, and internal AUREM paths (/app/backend/services/, /app/backend/routers/, /app/backend/.env, /app/memory/tier1/2/, /etc/supervisor/).
    - Internal path block `is_internal_path`: file-read tools (view_file/view_bulk/view_dir/safe_edit) refuse /app/backend/* paths from developer tenants.
    - All four guards wired into `ora_tools.invoke_tool` so they fire on every developer-initiated tool call (carries `_dev_user_id` in args).
    - 3 new tenant endpoints: POST /api/developers/session/acquire, POST /api/developers/session/release, GET /api/developers/sessions.
  Part 4 — Email sequence (new services/developer_email_sequence.py):
    - APScheduler cron daily 05:00 UTC, job id `aurem_dev_email_sequence`.
    - 4 buckets: day3_github_nudge (only if GitHub not connected, days 3-7), day7_unused (tokens_total_used==0, days 7-25), day7_halfway (tokens_remaining < 500 AND used > 0), day25_expiry (days 25-32).
    - Renders branded HTML (dark theme, same shell as Day-0 welcome) + plain-text fallback for each bucket; deep links to dashboard / connect / tokens pages.
    - Idempotent — stamps `email_sequence_sent[bucket_id]` on the account so cron re-runs never re-fire.
    - Best-effort audit row in `developer_email_sequence_log`.
    - Founder-trigger endpoint `POST /api/admin/developers/email-sequence/run` so the cron can be fired manually.
  Part 6 — Stale tier-1 loader test repair:
    - test_iter327n: 3 tests rewritten against the new folder-driven loader API (`last_injection_manifest()` instead of removed `_TIER1_FILES` constant; new normalized labels — `ZERO HALLUCINATION CHARTER`, `ORA MISTAKES LESSONS` etc).
    - test_iter329: 2 tests updated — file path moved /app/memory → /app/memory/tier1, assertion checks the folder discovery manifest rather than the truncated assembled block.
  Full active regression: **401 / 401 GREEN** across iter 327d → 331e (was 355/359 last iter; all 4 previously-stale assertions now green + 42 new iter-331e cases all green). Backend boots cleanly post-restart, /api/health 200.
Blocker: none
Next:
  - Batch B (next context window): all 8 developer frontend pages + landing-page hero + /developers/examples + /developers/status.
  - Batch C (third context window): Stripe — products, checkout, webhook, failed-payment downgrade with 3-day grace, invoice emails. Stripe test key is in pod env per platform policy.
  - User: push iter 331e to GitHub via "Save to Github" button.
Cost: $0.00 USD (pytest + lint only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T00:30:00Z
---

