# AUREM — Product Requirements Document

> Last updated 2026-05-24 (iter 332b D-6)

## Vision

AUREM is Canada's Autonomous Business Operating System for SMBs.
Polaris Built Inc., Mississauga, Ontario. PIPEDA + Law 25 + GDPR
compliant. Sovereign data residency, plain-English communication
("Rule Zero"), zero silent failures.

## Personas

- **Founder (Tejinder)** — operates entire platform via ORA / AUREM CTO chat.
- **Canadian SMB customer** — books jobs, recovers leads, runs ops on autopilot.
- **Developer (BYOK tenant)** — builds with the AUREM CTO API using their own LLM keys.
- **Enterprise procurement** — needs SOC 2, SLA, MSA, SSO, SCIM, residency.

## Core Requirements

1. **Rule Zero** — plain English, 1–3 sentences in chat. No JSON/code/tracebacks.
2. **Test-driven** — pytest required for every iter; full active suite must stay green.
3. **Portability** — every URL/credential lives in .env; production ≡ preview.
4. **PIPEDA + Law 25 default** — Canadian residency, anonymized network telemetry, consent.
5. **No silent failures** — every error must surface in unified_audit_log.

## What's been implemented (chronological highlights)

See `/app/memory/tier1/progress.md` for the full ledger. Highlights:

- iter 331c: Sprint 6 — consent network, ora_session_metrics, Vanguard, portability audit.
- iter 331d: Developer Portal foundation (signup/OTP/BYOK/tokens) + Day-0 welcome email.
- iter 331e: Security guards (SSRF, file caps, session limits, output masking) + email sequence.
- iter 331f: Developer Portal frontend (10 pages) + AUREM CTO brand swap.
- iter 331g: Beta ticker, Swagger UI, Stripe (Starter/Builder/Pro packages + webhook).
- iter 332a: Emergent Specialist Swarm (validated-solutions cache, auto-escalation, smart routing).
- iter 332b Batch A: Enterprise foundation (unified_audit_log, /enterprise leads, admin UI shell).
- iter 332b Batch A-2: Enterprise Admin UI (branding, domain, API keys, overview dashboard).
- iter 332b Batch A-3 / B: Production auth fix (AdminGuard JWT exp check, logout revoke),
  Organizations entity, SAML SSO config storage, SCIM provisioning.
- iter 332b Batch B-2: Full python3-saml ACS handler.
- iter 332b Batch C: Data residency (CA default), SOC 2 PDF, SLA + MSA page.
- iter 332b C-2: Trust Center page, Compliance admin UI, Org Switcher sidebar.
- iter 332b C-3: Footer Trust Center link, SSO/SCIM settings UI, SOC 2 email lead gate.
- iter 332b D: Renewal Telegram nudges, SAML SP-side AuthnRequest signing.
- **iter 332b D-6 (this slice)**: Dev portal admin bypass actually works (decode_token bug),
  DevDashboard crash fix (undefined `purchases`), smart Sign-In redirect on homepage,
  System Overview public router actually mounted in registry.

## Active regression status

**721 / 721 GREEN** across iter 327d → 332b D-15.

## Latest slices

- **D-6**: dev portal admin bypass + DevDashboard crash + smart sign-in + System Overview public wiring.
- **D-7**: /admin/developer-signups page + real-time Telegram nudge.
- **D-8**: 24h sparkline on cockpit Pulse tile + CSV export.
- **D-9**: /developers/login page.
- **D-10**: AUREM CTO chat panel on dev dashboard + token-low popup + Connect rebuilt + expanded BYOK.
- **D-11**: Free tier moved to OpenRouter (one key, 3-model ladder).
- **D-12**: Roman-coin background image on dev portal.
- **D-13**: Collapsible dev portal sidebar (persisted to localStorage).
- **D-14**: Cloudflare 524 hardening — 28s per-model timeout + paid Llama/Mistral rungs + safe HTML-response parsing + trimmed history budget.
- **D-15**: SSE streaming for the dev chat — typing-out UX, 10× faster perceived latency. Includes happy-path, fallback, error, and token-wall test coverage.
- **D-30**: Pillar 4 false-red fix + Developer self-deploy (SSH + Docker) + Domain linking wizard + CTO chat copy button.
- **D-31** (PARKED on branch): `/app/aurem_cto/` isolated module skeleton (deploy + domain + chat-commits + unlock + vault). 3/3 isolation tests pass. Re-enable when onboarding ships.
- **D-32 (this slice)**: Build-first onboarding — Watchdog-approved scope pivot.
  - `/my/projects/new` is the new post-signup landing (no GitHub/server/domain prompts).
  - Multi-tenant FastAPI preview at `preview.aurem.live/<project-id>` rendering an inline manifest.
  - Token wallet: 1000 signup grant, cheap=1 / frontier=5, atomic conditional decrement (HTTP 402 with balance + cost on over-spend).
  - Social-share scrape (`+2500` on auto-approve) with admin pending queue + manual decide endpoint.
  - Go-Live checklist component (GitHub / server / domain / BYOK) — locked dashed-card until `progress >= 0.80`, unlocked green card after.
  - DevSignup + DevLogin redirect to `/my/projects/new` instead of `/developers/connect` and `/developers/dashboard`.

## Backlog (P0 → P2)

### P0 — Production
- **Push to GitHub → redeploy aurem.live**. Prod is 6 batches behind (A-3 → D-6).
  Every redeploy day means broken-logout sessions in prod + missing Trust Center
  + dead admin /developers bypass + dashboard crash.

### P1 — Next slice
- GitHub OAuth flow for one-click connect (PAT already shipped in D-30).
- Real Atlas cluster-move automation for residency change requests
  (currently queues to `residency_change_requests` for manual ops).
- Backfill historical rows from 5 legacy audit collections into
  `unified_audit_log` (APScheduler job, ~40 LOC).
- Public "subprocessor changelog" RSS feed.

### P2 — Backlog
- RBAC complete wiring across ~80 routers — dedicated 2–3 day slice,
  new `user_rbac.py` with Owner/Admin/Developer/Viewer hierarchy.
- Pro tier recurring auto-renew (Stripe subscription mode swap).
- Service-account Google Calendar API for shared staff calendar.
- Friendlier 404 for stale ghost-* slugs.
- ConsentToggleCard shadcn → av2-card cleanup (20 LOC).
- SCIM PATCH partial-update + Groups endpoint.
- SP cert rotation playbook (current 10-year cert; calendar reminder at year 8).

## Architecture

- React SPA + FastAPI + MongoDB.
- Background tasks: APScheduler (renewal nudges, email sequence, sandbox cleanup, Vanguard).
- 3rd-party: Stripe (test+live key in pod env), Resend, Telegram, python3-saml, reportlab.

## Key endpoints (latest)

- `GET  /api/public/system-overview/stats` — public mirror (iter 332b D-6 wired).
- `GET  /api/developers/me` — accepts admin JWT (iter 332b D-6 fixed).
- `GET  /api/developers/me/purchases` — recent 3 payment_transactions.
- `POST /api/saml/{org_id}/acs` — full python3-saml validation.
- `GET  /api/compliance/{org_id}/soc2.pdf` — SOC 2 export.
- `POST /api/compliance/soc2/sample` — lead-gated PDF for Trust Center.
- `POST /api/enterprise/leads` — public contact-sales form.
- `POST /api/auth/admin/logout` — refresh-token revocation.

## Test credentials

See `/app/memory/test_credentials.md`.
