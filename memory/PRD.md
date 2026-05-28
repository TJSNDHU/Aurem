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
  - **Chat ↔ wallet ↔ progress wired**: `/api/developers/cto/chat/stream` accepts `project_id` + `model_tier`, debits the wallet atomically, parses `progress:` / `phase:` / `MANIFEST_PATCH:{…}` markers (balanced-brace JSON extractor) from the LLM reply, and emits `insufficient_tokens` SSE error when wallet is dry. PROGRESS CONTRACT added to the AUREM CTO system prompt.
  - Public preview at `/preview/:project_id` (no auth) reading the public manifest endpoint with 6s live-refresh.
- **D-33 (this slice)**:
  - **Stripe paywall UI gate**: `PaywallBlock` component renders inside the `insufficient_tokens` assistant message with one CTA to `/pricing` (existing Builder/Pro tiers) and one shortcut to `/my/projects/new#share` for the 2500-token earn flow. Zero new Stripe integration.
  - **Preview hosting setup doc**: `/app/aurem_cto/docs/PREVIEW_HOSTING_SETUP.md` — exact DNS A record + Caddy block + verification commands for `preview.aurem.live` (user runs on prod box).
  - **DB scan** completed before any gap code — 38 shadcn components, tailwind config live, parallel referral/wallet/deploy/health systems mapped, Docker templates already at `/app/aurem-cto/` (hyphen folder, distinct from D-31 underscore folder).
  - **AUREM CTO module re-enabled** — fixed sys.path init in registry block so `/aurem-cto/*` routes mount on boot. Verified by GET `/aurem-cto/vault/audit-log` returning HTTP 200.
  - **UI fix 1**: hover-reveal Preview + Deploy buttons on every assistant message that contains a code change (fenced ```code```, MANIFEST_PATCH, or `[step N/M]`). Mobile fallback via `@media (hover: none)`. Test-ids `dev-cto-preview-btn-<idx>` + `dev-cto-deploy-btn-<idx>`.
  - **UI fix 2**: auto-expanding chat textarea grows from 1 row up to 40vh, then scrolls inside. JS resize handler runs on every change.
  - **Gap 1 (Codebase Indexer)**: `aurem_cto/services/codebase_indexer.py` — pulls customer repo via existing BYOK PAT, indexes routes/models/components/deps, exposes `build_context_block(user_id)` which the chat-stream now injects as a system message before every turn.
  - **Gap 2 (Stack Selector)**: 4 templates at `aurem_cto/templates/stacks/` (react-fastapi default + nextjs-node + vue-express + plain-html), each with `docker-compose.yml` + `README.md`. Stack selector grid renders on `/my/projects/new`; `stack` field saved on project doc.
  - **Gap 3 (Trust Signals)**: `aurem_cto/routers/trust.py` — `/aurem-cto/trust/deploy-count` (aggregates 5 legacy collections), `/aurem-cto/trust/uptime` (24h % from `external_uptime_pings`), `/aurem-cto/gallery` (opt-in showcase). New collection `aurem_cto_public_gallery`. Public `/gallery` page lives at `PublicGallery.jsx`.
  - **Gap 4 (Engagement)**: `aurem_cto/routers/engagement.py` — `/aurem-cto/referrals/my` (ref link = `aurem.live/?ref=<user_id>`, reuses `referrals` + `verified_referrals`), `/aurem-cto/streak/me` (consecutive daily debits from `onboarding_token_wallets.ledger`). Streak chip + gallery toggle render on workspace header.
  - **Tests**: 9/9 in `/app/aurem_cto/tests/` green (3 isolation + 6 gap regression).
  - **Module isolation maintained** — 3 host imports declared; new whitelist entry for `aurem_cto_public_gallery` + 7 read-only host collections (developer_accounts, onboarding_*, referrals, external_uptime_pings) documented in the isolation test.
- **D-35 (this slice — Dogfood: aurem.live as a project)**:
  - **`is_production_dogfood` flag** on `onboarding_projects` with `production_warning`, `github_repo_url`, `production_host` fields. View serializer exposes them.
  - **Admin endpoint** `POST /api/onboarding/projects/dogfood/aurem-live-init` — idempotent seed of the `aurem-live-production` project for the calling admin. Skips the preview surface (`preview_url=""`), sets `progress=1.0`/`phase=production`/`domain.done=true` (aurem.live already lives). Non-admins blocked (401/403).
  - **Status endpoint** `GET /api/onboarding/projects/dogfood/aurem-live-status` — returns `github_linked`, `deploy_configured`, `indexer_fresh`, `last_dry_run`, `last_real_run`, `real_deploy_unlocked`.
  - **Dry-run deploy mode** added to `/aurem-cto/deploy/run` — runs `git fetch && docker compose config --quiet && echo DRY_RUN_OK` (no `git pull`, no `up -d`). Safe staging check.
  - **Production guard** — for projects with `is_production_dogfood=true`, a real `deploy` or `revert_to` is rejected with HTTP 409 `dry_run_required` unless a `dry_run` status=ok run exists for the same user within the last 24h. `rollback` stays unrestricted (emergency exit).
  - **Indexer fix** — `_fetch_user_pat` now reads `developer_github_links.pat_enc` (where `/api/developers/github/link` actually writes) with `developer_accounts` as legacy fallback. `_fetch_user_repo_url` prefers the project's saved repo URL.
  - **Frontend `ProjectWorkspace`** — red production-warning banner at top when `is_production_dogfood`, preview card hidden, new `DogfoodDeployPanel` showing GitHub/Server/Indexer pills + Refresh Index + Dry-Run + Real Deploy (gated on dry-run).
  - **Frontend `NewProjectFlow`** — admin-only `DogfoodSeedCard` (auto-hides on 403) with a one-click "Add aurem.live as project" button.
  - **Tests**: 5/5 new in `/app/backend/tests/test_dogfood_d35.py`; full active suite 20/20 green (5 D-35 + 6 D-32 + 9 aurem_cto isolation/gap).
  - **Status**: Scaffold complete. Real test deploy still needs the user to (1) paste GitHub PAT under `/developers/connect` → GitHub card, (2) save SSH host + private key under the Deploy card, then click "Refresh Index" and "Run dry-run deploy" inside the aurem-live-production workspace.
- **D-35-deploy-fix (2026-02)** — Production deploy logs showed `ModuleNotFoundError: No module named 'aurem_cto'`. Root cause: the package lived at `/app/aurem_cto/`, outside the backend container's shipped tree (only `/app/backend/` and `/app/frontend/` are packaged for Atlas-backed prod). Fix: **moved `/app/aurem_cto/` → `/app/backend/aurem_cto/`** so it ships with the backend image. Dropped the sys.path-mangling block in `registry.py` (now a plain `import aurem_cto`). `test_isolation.py` MODULE_ROOT now resolves from `__file__` instead of the hard-coded path. 20/20 tests still green; preview confirms `/aurem-cto/stacks` returns 200 after restart. **NO docker, supervisor, or env changes were needed.**
- **D-36 (2026-02 — AUREM Design System everywhere)** — Adopted Emil Kowalski's design-engineering rules as the *house style* for every LLM-emit surface across AUREM.
  - **`aurem_cto/prompts/aurem_design_system.md`** — full skill markdown (Sonner + Vaul mandate, animation decision framework, custom easing curves, `:active scale(0.97)`, popover origin awareness, reduced-motion + touch hover gates, performance rules, review-format table).
  - **`services/aurem_design_prompt.py`** — single shared loader (`get_aurem_design_prompt`, `inject_design_prompt`, `design_prompt_for_native_provider`) with sentinel marker `[AUREM-DESIGN-SKILL-v1]` for E2E asserts. Cached, idempotent, safe-fallback if markdown missing.
  - **Wired into every UI-emit path**: `services/dev_cto_chat.py` (AUREM CTO BYOK + free tiers + Anthropic + Gemini), `services/ora_brain.py` (ORA mode_2 code work), `services/aurem_ai_service.py` (every chat session created across the platform), `services/website_edit_worker.py` (customer-site HTML/CSS generator).
  - **Stack template baseline** — `aurem_cto/templates/stacks/react-fastapi/ui-design.css` ships with `--ease-out / --ease-drawer / --ease-in-out` curves, universal `:active scale(0.97)`, popover transform-origin override, Sonner toast easing, Vaul iOS drawer curve, `prefers-reduced-motion` guard. README updated to mandate Sonner + Vaul + lucide-react.
  - **Dogfood on aurem.live itself** — `frontend/src/styles/aurem-design.css` created and imported in `App.js` so the same rules render in production. Browser confirms `:root --ease-out` and `--ease-drawer` are live.
  - **Tests**: 9/9 new pytest in `test_design_skill_d36.py` (sentinel, idempotent injection, AUREM CTO BYOK path, AuremIntelligence session creation, stack template CSS + README, frontend CSS import). Full active suite **29/29 green**.
- **D-37 (2026-02 — Intent-aware AUREM CTO output contract)** — The single rigid prompt that forced `Plan + [step N/M] + NEXT_STEPS + progress + MANIFEST_PATCH` on every turn caused robotic replies for greetings, casual questions, and bug reports.
  - **`services/aurem_cto_intent.py`** — pure-heuristic classifier with 6 buckets (`build / question / conversational / diagnostic / strategic / unknown`). Zero extra LLM call per turn — ~0.1 ms latency. Each bucket has its own output-contract suffix appended as a system message tagged `[INTENT=<bucket>]`.
  - **Wired** into both `cto_chat()` and the SSE streaming path in `services/dev_cto_chat.py`. Latest user message is classified once, the matching suffix is inserted at index 1 of the messages list (right after the base AUREM CTO prompt, before the AUREM Design System suffix and the codebase context).
  - **Output contracts:**
    - *conversational*: 1-2 sentences, no markers, no NEXT_STEPS.
    - *question*: 1-3 paragraphs of plain English, no plan/steps, one NEXT_STEPS line.
    - *diagnostic*: root-cause first, then one fix with file path.
    - *strategic*: pull real numbers, 3 paragraphs or a table, decision-style chips.
    - *build*: full plan + step markers + progress + MANIFEST_PATCH + NEXT_STEPS (unchanged from D-32).
    - *unknown*: ask one clarifying question.
  - **Tests**: 34/34 new pytest in `test_intent_d37.py` (22 classifier table cases + 6 system-prompt-branch tests + 4 chat-integration tests verifying the right `[INTENT=...]` system message lands in the LLM message stack). Full active suite **63/63 green** across D-32 + D-33 + D-35 + D-36 + D-37 + aurem_cto isolation.
- **D-38 (2026-02 — Mobile sidebar · chat-button reorg · Admin Integration Health tracker)** — Four bundled fixes shipped in one batch.
  - **Mobile sidebar slide-in drawer** — `<DashboardShell>` now tracks `mobileSidebarOpen` state; a new hamburger in the topbar (`data-testid="dev-shell-mobile-menu"`) toggles the `av2-shell--mobile-open` class. CSS `@media (max-width: 767px)` block (in `styles/dashboard-theme.css`) makes `.av2-sidebar` `position: fixed; transform: translateX(-105%)` by default and slides it in on the modifier class with the iOS drawer curve. Backdrop click + route change auto-dismiss. Hamburger hidden ≥768 px.
  - **Chat panel button reorg** — replaced the hover-only `MessageActionButtons` (Preview/Deploy) with two pieces: a permanent `BubbleActionRow` (Copy + Rollback side-by-side) bottom-right of every assistant bubble, AND a new `ChatFooterActions` bar (Preview + Deploy) above the input. Solves the overlap with Copy on hover that customers reported. Rollback calls `/api/developers/deploy/run` with `mode=rollback,message_id=…` and gracefully routes to `/developers/connect#deploy` if the deploy target isn't configured.
  - **Admin Integration Health tracker** — `routers/admin_integrations_router.py` (admin-only) returns `summary` + 17 integrations across 5 groups (LLM, comms, payment, data, infra) with per-provider `status` pill (green/yellow/red/unset), `key_tail` (last 4 chars only — full key never leaked), `failures_24h` + `failures_7d` (with bucket breakdown), `last_failure_at`, `needs_recharge` boolean, plus `recharge_url` / `docs_url` links. Reads `api_key_health_log` written by `services/api_key_health_watcher.py`. Path `/api/admin/integrations/integrations/*` excluded from the 90-second boot-grace shortcut in `middleware/health_probe.py` (would otherwise return 204 No Content for the first 90 s). New admin page at `frontend/src/platform/AdminIntegrations.jsx`, routed at `/admin/integrations`, linked from `AdminShell` sidebar.
  - **Live campaign diagnosis (preview)** — endpoint returned 17 integrations: 7 healthy (openrouter, emergent_llm, twilio, telegram, stripe, tavily, cloudflare), 9 unset (anthropic, openai, gemini, whapi, sendgrid, linkedin, scrapingbee, hetzner, github_bot), 1 red (resend; from planted test row).
  - **Tests**: 7/7 `test_admin_integrations_d38.py` (auth gate, shape contract, key-leak guard, unset detection, 401-promotes-to-red, group coverage) + 5/5 `test_mobile_sidebar_d38.py` (CSS @media block present, hamburger testids, chat-button reorg, admin page + route wired). Full active suite **75/75 green**.
- **D-38 path-fix** — `aurem_cto` import in `registry.py` was failing in preview because cwd=/app there; D-35 fix only worked for production cwd=/app/backend. Registry now resolves `_backend_root` from `__file__` and prepends to `sys.path` so the plain `import aurem_cto` succeeds in BOTH environments.
- **D-39 (2026-02 — AUREM CTO self-awareness + language mirroring + anti-fabrication)** — Customer reports: AUREM CTO answered "how do you work" with a generic textbook workflow (component tree → state mgmt → tests → handoff), included Python pseudo-code, claimed it found "185 bugs across 22 rounds" (fabricated), and said it has no internet (false). Three fixes shipped:
  - **Base SYSTEM_PROMPT** in `services/dev_cto_chat.py` gained a "WHAT YOU ACTUALLY ARE" block listing the real architecture (intent classifier, AUREM Design System injection, codebase indexer, Tavily web search, dry-run + rollback deploy, 75+ pytests, token wallet 1/5 with 1,000-grant signup) so the LLM has facts to ground introspective answers in.
  - **Anti-fabrication rule** with explicit "185 bugs" negative example: *"NEVER fabricate numbers ... If a stat is not in your context or the codebase index, say so plainly: 'I don't have that number in front of me — want me to look?'"*. Also added "Code blocks are only for code you're producing — never for explaining your own thinking" to kill the Python-pseudo-code tic.
  - **Language mirroring** rule: match the developer's language (Hinglish, Hindi, French, Spanish, Punjabi), keep an English trailer in `(en: …)` so the founder reading logs can still scan quickly.
  - **Intent classifier** in `services/aurem_cto_intent.py` gained `_INTROSPECTIVE_RE` that catches English ("how do you work", "your workflow", "what can you do") AND Hinglish ("tum kaise kaam karte ho", "aap kya kar sakte ho"). Introspective phrasing now ALWAYS routes to `question` even when keywords like "plan" or "workflow" would otherwise hit the build bucket.
  - **Question branch prompt** updated to point the LLM at the base prompt's "WHAT YOU ACTUALLY ARE" block when the question is about the platform itself.
  - **Tests**: 14/14 new pytest in `test_self_awareness_d39.py` (architecture block present, fabrication rule + negative example present, language mirroring rule present, code-block-restriction present, 9 introspective phrases route to `question` across English + Hinglish, question branch references "WHAT YOU ACTUALLY ARE"). Full active suite **89/89 green** (D-32 + D-33 + D-35 + D-36 + D-37 + D-38 + D-39 + aurem_cto isolation).
- **D-40b (2026-02 — Founder caught LLM still dumping illustrative Python pseudo-code to a meta question)** — D-39 strengthened the prompt against fabricated stats, but free-tier deepseek/llama still wrote `def distill_idea(...)` + `patterns = {...}` to "illustrate" its own non-tech reply style. Fix is defense-in-depth, two layers:
  - **Prompt layer** — added an `ABSOLUTE RULE — ILLUSTRATIVE PSEUDO-CODE IS BANNED` block as the FIRST rule after the role line in `services/dev_cto_chat.py::SYSTEM_PROMPT`. Lists negative examples (`def distill_idea`, `if customer_type ==`, `patterns = {...}`) and positive replacements (numbered list, analogy, quoted prose dialogue). Explicitly: code blocks are ONLY legal when producing real code for the dev's actual project.
  - **Output-guard layer** — new `services/aurem_cto_output_guard.py::strip_illustrative_code(reply, *, intent, non_technical)`. For any non-build intent (`question / conversational / strategic / unknown / diagnostic`) OR whenever `non_technical=True`, every fenced block that looks Python/JS-ish (lang tag or `def/if/return/dict-literal` heuristic) is replaced with a single-line breadcrumb so paragraph flow survives. JSON/yaml/text fences are preserved. Wired into BOTH `cto_chat` (post-dispatch) AND `cto_chat_stream` (buffer-and-sanitize for non-build turns; build turns still stream live token-by-token).
  - **Tests**: 9/9 new pytest in `test_non_tech_no_code_d40b.py` (founder's exact prompt → `question` + non-tech True, guard strips all 3 Python blocks for question intent, guard strips when non_technical=True even with intent=build, guard preserves build replies for tech devs, guard preserves JSON config fences, guard is idempotent + handles empty/None). Full active suite **82/82 green** across the D-36→D-40b iter ring.
- **D-41 (2026-02 — AUREM-first rule, ban external dev tools in AUREM CTO replies)** — Founder caught AUREM CTO replying with a "Tools I Use" table that recommended Figma + Vercel + CodeSandbox + JSON Server + Mock Service Worker + Loom — sending customers *off* the platform. Defense-in-depth, two layers same as D-40b:
  - **Prompt layer** — added `AUREM-FIRST RULE — NEVER SUGGEST EXTERNAL DEV TOOLS` block to `SYSTEM_PROMPT` listing 7 banned tool categories (Figma/Sketch/Penpot for design, Vercel/Netlify/Heroku/Railway/Render/Fly.io for hosting, CodeSandbox/StackBlitz/Replit for sandboxes, Bolt.new/Lovable/V0/Cursor/Windsurf for AI build, MSW/JSON Server/Mockoon for mock APIs, Loom for share-back, Postman/Insomnia for API testing) with AUREM-native equivalents (AUREM Design System, preview.aurem.live, AUREM Deploy, public preview link, stack template mock_backend=true, /api/docs). Exempts upstream dependencies the dev already chose (GitHub, Docker, Stripe, AWS).
  - **Output-guard layer** — `services/aurem_cto_output_guard.py` gained `append_aurem_first_correction(reply)` and `apply_output_guards(reply, intent, non_technical)`. Detects banned tool names paired with recommendation verbs (use/try/recommend/host/deploy/prototype-in) within a 60-char window, OR a "Tools I Use / Recommended Tools" blanket header. Appends a non-destructive `[AUREM-FIRST CORRECTION]` footer mapping each banned tool → AUREM equivalent. Idempotent. Wired into both `cto_chat()` and `cto_chat_stream()` BUILD and non-build paths.
  - **Streaming UX** — build turns keep live token-by-token streaming; correction footer arrives as one final token event when banned tools were detected. Non-build turns buffer-and-sanitize as before.
  - **Tests**: 12/12 new pytest in `test_aurem_first_d41.py` (system prompt has rule + ban list + equivalents, correction fires on founder's caught reply, idempotent, no-op on safe replies, catches Vercel/CodeSandbox/Bolt/Lovable/V0, integration test with combined pseudo-code + tool-suggestion). Full active suite **85/85 green** across D-36→D-41 iter ring.
- **D-42 (2026-02 — GitHub OAuth one-click "Connect with GitHub")** — Founder asked to replace the 7-step PAT-paste flow with a 3-step OAuth popup. PAT stays as fallback below an "or paste a token manually" divider so users on environments without `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` configured aren't blocked.
  - **Backend**: `routers/developer_portal_router.py` gained `GET /api/developers/github/oauth/start` (mints CSRF `state` + PKCE S256 challenge, persists to new `developer_github_oauth_states` collection, returns the GitHub authorize URL with `scope=repo read:user`) and `GET /api/developers/github/oauth/callback` (validates state — one-time use, 10-min TTL — exchanges `code` via `httpx`, fetches `/user`, upserts encrypted access_token into the existing `developer_github_links` collection so the codebase indexer + deploy pipeline keep working unchanged with `auth_method="oauth"`). Returns a self-closing HTML popup page that `postMessage`'s the opener with `source: "aurem-github-oauth"`.
  - **Required env**: `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` (admin task — register OAuth App at github.com/settings/developers). Optional `GITHUB_OAUTH_REDIRECT_URI` (defaults to `{base_url}/api/developers/github/oauth/callback`).
  - **Frontend**: `DevConnect.jsx` `GitHubConnectCard` now renders the new `OneClickGitHubOAuth` button at the top (dark GitHub-style pill, lucide Github icon, `:active scale(0.97)`, popup centered, listens to `window.message`). PAT input stays below an "OR PASTE A TOKEN MANUALLY" divider. Returns helpful error when admin hasn't set credentials yet.
  - **Tests**: 9/9 new pytest in `test_github_oauth_d42.py` (503 when env unset, persists state + emits well-formed authorize URL with PKCE, respects custom redirect_uri env, callback rejects missing/invalid/expired state, propagates GitHub error param, happy path persists encrypted token + consumes state, handles token-exchange HTTP failure). Full active suite **94/94 green** across D-36→D-42 iter ring.
- **D-43 (2026-02 — Founder-controlled platform secrets UI + Maxx toggle + Planning bar + sidebar widgets)** — Massive UI/UX parity slice. Replaces the "edit .env on the server" workflow with a UI page, surfaces token balance + GitHub status + model-tier toggle in the sidebar, and promotes the AI's NEXT_STEPS to a top-of-chat Planning Bar.
  - **Backend `routers/platform_secrets_router.py`** — admin-gated `GET/PUT/DELETE /api/developers/settings/secrets[/{name}]`. Whitelist of 19 secret names (LLM providers, comms, payment, data, infra, GitHub OAuth). AES-256 (Fernet via `services.credential_crypto`) at rest. PUT also applies plaintext live to `os.environ` so every existing code path picks up the new key without a restart. New collection `platform_secrets`. Boot hook `apply_platform_secrets_to_env()` re-applies DB rows to env on every backend start. Wired in `routers/registry.py` next to admin-integrations.
  - **Frontend `PlatformCredentialsBlock.jsx`** — embedded at the top of `/developers/settings`. One row per whitelisted secret with group headers (GitHub, LLM, Comms, Payment, Data, Infra). Green dot = set, show/hide eye toggle, Save button with success flash, Delete (only enabled when source=db), env-set keys read-only. Encryption-warning banner when `AUREM_ENCRYPTION_KEY` is not set.
  - **Sidebar widgets `DeveloperShell.jsx`** — between nav and saved projects: (1) GitHub status pill with green dot when connected, (2) Maxx toggle (`Zap` icon, ON = frontier-model 5/turn, OFF = cheap 1/turn) — gated on `balance >= 5`, persists to localStorage, broadcasts `aurem-maxx-toggle` CustomEvent so the chat composer mirrors state, (3) Token progress bar (% of 1000-grant cap, low-state warning under 200). All three collapse to compact icons in the collapsed sidebar.
  - **Planning Bar `DevCtoChatPanel.jsx`** — moved NEXT_STEPS chips from below the input to the TOP of the chat panel as "Planning the next move…" + 3 chips with leading `+` button + `✕` dismiss icon. Pulsing dot (new `@keyframes aurem-pulse` in `dashboard-theme.css`) when streaming. Resets dismiss state when a new assistant turn produces fresh NEXT_STEPS.
  - **Maxx composer button** — between textarea and Send. Mirrors sidebar toggle via the shared CustomEvent. When ON, the stream POST body forces `model_tier=frontier`; OFF falls back to the prop value or `"cheap"`.
  - **Tests**: 6/6 new pytest in `test_platform_secrets_d43.py` (whitelist enforced, save persists encrypted envelope + applies to env, list never returns plaintext, delete clears DB + env, boot-hook reload from DB, env-only secrets still listed with source="env"). Full active suite **100/100 green** across D-36→D-43 iter ring. Frontend lint clean.
- **D-44 (2026-02 — Sidebar restructure + 3 new pages: Deploy / Domain / Database)** — Founder-spec sidebar with 4 grouped sections + 3 new Build-section pages backed by existing + 1 new admin endpoint.
  - **Sidebar `DeveloperShell.jsx`** — `DASH_NAV` now grouped: MAIN (Home), BUILD (Connect / Projects / Deploy / Domain / Database), DEVELOPER (Analytics / Examples / Tokens / API Docs / Status), ACCOUNT (Settings / Terms). Section labels render as small uppercase rows; collapse to 1px dividers in compact mode. Connect icon changed from `Github` → `Plug`. Projects route added as alias to Dashboard (`/developers/projects` → DevDashboard).
  - **`/developers/deploy` (`DevDeploy.jsx`)** — app thumbnail card with Rocket logo + aurem.live link + `Redeploy` button (POST `/api/developers/deploy/run`), live progress steps (Environment Ready → Building → Migrate DB → Export Secrets → Deploy → Health Check), recent deploys list from `/api/developers/deploy/history` (status dot + short run-id + mode + started_at).
  - **`/developers/domain` (`DevDomain.jsx`)** — 2 client-side toggles (Allow search engine crawling, Redirect root → www, persisted to localStorage), link form (domain + server IP) → `/api/developers/domain/config`, current-domain card with DNS records pre block.
  - **`/developers/database` (`DevDatabase.jsx`)** — admin-only read-only card. App name, provider, masked Mongo URL with show/hide eye, copy-to-clipboard, "Go to database" link to Atlas. Plaintext URL is NEVER sent to the client.
  - **Backend `routers/developer_database_router.py`** — new `GET /api/developers/database/info` (admin-gated). `_mask_mongo_url` helper strips `user:pass` and truncates host body, returns `mongodb+srv://****:****@clus…db.net/aurem`. Wired in `registry.py` next to platform-secrets.
  - **Merge**: BYOK rotate section removed from `DevSettings.jsx` (now lives next to BYOK paste form on `/developers/connect`). PlatformCredentialsBlock + sessions list + consent + danger-zone remain on Settings.
  - **Tests**: 7/7 new pytest in `test_dev_database_d44.py` (4 mask-helper edge cases, db_info masks credentials + raises 503 when MONGO_URL missing, sidebar nav constant exposes all 13 D-44 routes, DevSettings no longer has BYOK-rotate testid). Full active suite **108/108 green** across D-36→D-44 ring. Lint clean. Backend healthy (`/api/health` 200, `/api/developers/database/info` 401 unauthed as expected).
- **D-45 (2026-02 — Wire Deploy progress to real backend log stream + confirm Fork button absence)** — Replaced the client-side timer animation on `/developers/deploy` with a real log poller, and locked the "no Fork button" requirement with a regression test.
  - **Frontend `DevDeploy.jsx`** — exported pure helper `classifyStep(line)` maps a single deploy-log line to a step index 0-5 by matching anchors (`$ ` → 0, `git `/`from origin` → 1, `compose pull`/`pulling ` → 2, `creating`/`recreating` → 3, `started`/`running` → 4, `deploy_head=` → 5). New `startPolling(runId)` walks `/api/developers/deploy/log/{run_id}?since=<cursor>` every 900ms, monotonically advances `stepIdx` (never rewinds), keeps a tail of the last 60 lines in a `deploy-log-tail` `<pre>` console. On `status != "running"` the poller stops and either marks all steps complete or surfaces the failure + exit code.
  - **Tests**: 5/5 new pytest in `test_deploy_log_wire_d45.py` (deploy command still emits `git fetch` + `docker compose pull` + `DEPLOY_HEAD=` anchors so frontend classifier stays correct, `/deploy/log/{run_id}` endpoint signature unchanged with documented keys, DevDeploy keeps all classifier anchors, log-tail panel testid present, **no Fork button anywhere in `/app/frontend/src`** — scans for JSX `>Fork<` text + `GitFork` lucide imports + `data-testid="fork-…"`). Full active suite **113/113 green** across D-36→D-45 ring. Lint clean.
- **D-46 (2026-02 — One-click security-key generation + admin oversight)** — End-to-end security feature: customer one-click mints fresh `JWT_SECRET` + `AUREM_ENCRYPTION_KEY` + `CORS_ORIGINS`, AES-256 at rest, applied live to `os.environ` (no restart). Admin panel shows every customer's status, force-rotate available, plaintext never traverses the admin path.
  - **Backend `routers/security_keys_router.py`** — `POST /api/developers/security/generate-keys` (auth-gated) mints the triplet via `secrets.token_urlsafe(48)` + 32-byte b64 + literal `https://aurem.live`, marks any prior `active` row for the same user as `rotated`, stores AES-256 envelope per key (key-tail tracked), captures source IP, returns plaintext ONCE + applies live to env. `GET /api/developers/security/status` returns masked summary only. Admin: `GET /api/admin/security-keys` (aggregates by user), `GET /api/admin/security-keys/{user_id}/history`, `POST /api/admin/security-keys/{user_id}/rotate` (records `rotated_by_admin` + `rotation_reason`). Plaintext NEVER traverses the admin path.
  - **Frontend `SecurityKeysBlock.jsx`** — sits at the top of `/developers/settings` above `PlatformCredentialsBlock`. Generate/Rotate button with confirm prompt, plaintext-once panel with per-row Copy + Show/Hide + acknowledge-checkbox-gated dismiss. Below: tail-only masked summary card.
  - **Admin panel `AdminSecurityKeys.jsx`** at `/admin/security-keys` — 3 summary tiles (total / active / rotated), customer table, inline rotation-history drawer. Force-rotate prompts for reason.
  - **Bugfix `routers/_registry_lean_prune.py`** — narrowed `/api/admin/security` prefix-prune to exact-match (it was sweeping the D-46 admin routes); moved orphan subscription_router endpoint to `_PRUNE_EXACT` so its prune behavior is preserved.
- **D-47 (2026-02 — Save-to-GitHub dialog + per-turn model badge + security-rotation alerts)** — Three frequently-requested features shipped in one slice.
  - **Backend `routers/github_save_router.py`** — three endpoints, all gated by `require_auth`. `GET /api/developers/github/repos` lists the user's repos via `/user/repos` (per_page=100, sorted by updated, owner+collaborator). `GET /api/developers/github/repos/{owner}/{repo}/branches` lists branches. `POST /api/developers/github/commit` reads the project's `onboarding_projects` row + `dev_cto_chats` history, builds `aurem/<project_id>/manifest.json` (JSON manifest) and `aurem/<project_id>/aurem-chat.md` (full history as markdown with `### USER`/`### ASSISTANT` headers), looks up each path's existing SHA, then PUTs both via `/repos/{owner}/{repo}/contents/{path}`. Uses the OAuth/PAT token persisted by D-42 (`developer_github_links.pat_enc`, decrypted via `services.byok_store`).
  - **Frontend `SaveToGithubDialog.jsx`** — modal dialog with 4 states: `pick` (repo dropdown loaded from `/repos` + branch dropdown loaded from `/branches` + commit-message input + Cancel/Save buttons), `saving`, `success` (big Github icon + "Successfully saved to GitHub!" + repo/branch/commit-sha + "View on GitHub" link + "Okay got it" close button), `error` (with Try-again). Connected-account green pill at the top.
  - **Chat composer button** — `data-testid="dev-cto-chat-save-github"` sits next to the Maxx pill; disabled until a project is loaded. Mounted as `<SaveToGithubDialog open={…} projectId={…} onClose={…} />` near `<LowBalanceModal>`.
  - **Per-turn model badge** — chat panel now stamps `{provider, model, tier}` onto each assistant message when the `meta` event arrives. Rendered as a small JetBrains-mono pill under the bubble content (`dev-cto-msg-model-badge-{i}`); orange for free tier, gold for BYOK, tooltip shows full `provider · model`.
  - **Security-rotation alerts `services/security_alerts.py`** — best-effort, never raises. Two channels (env-gated):
    - Slack via `SECURITY_ALERT_SLACK_WEBHOOK` (incoming-webhook URL)
    - Email via Resend (`SECURITY_ALERT_EMAIL` recipient + existing `RESEND_API_KEY`)
    Hooked into `security_keys_router.generate_security_keys` (fires `self_rotated` ONLY when a prior `rotated` row exists, so first-time generation is silent) and `admin_force_rotate` (fires `admin_force_rotated` with `reason` + `ip_address`). Optional `SECURITY_ALERT_FROM` env var customizes the From: address (default `alerts@aurem.live`).
  - **Tests**: 7/7 new pytest in `test_save_github_d47.py` (repos 401-when-unlinked + happy path, branches happy path, commit writes 2 files with valid JSON manifest + readable markdown chat, commit 401-when-unlinked, alerts no-op when unconfigured, alerts fire Slack with payload containing user + reason + IP). Full active suite **130/130 green** across D-36→D-47 ring. Lint clean (Python + JS). Backend healthy on preview (`/api/developers/github/repos` and `/api/developers/github/commit` both 401 unauthed as expected).

  - **Tests**: 10/10 new pytest in `test_security_keys_d46.py` (triplet randomness, generate returns plaintext-once + applies to env + tails match, rotate marks old row, status hides plaintext, admin list aggregates + hides plaintext, history returns all rows, force-rotate inserts new active row + records reason, 404 on rotate-with-no-keys, 503 when DB missing). The crypt_key fixture pre-touches `JWT_SECRET`/`CORS_ORIGINS` via monkeypatch so test-driven env mutations don't leak into D-38's JWT assertions. Full active suite **123/123 green** across D-36→D-46 ring. Lint clean. Backend healthy on preview (`/api/developers/security/status` 401, `/api/admin/security-keys` 401, `/api/admin/security` 404 as expected).


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
