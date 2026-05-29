# SPEC 02 — Technical Requirements Document (TRD)

> Read third. Updated 2026-05-28, iter D-57.
>
> Long-form system architecture diagram (mermaid) + full 26-service
> integration table: `ARCHITECTURE.md` (REFERENCE, iter 287.7).
> 29-tool ORA catalog: `SYSTEM_OVERVIEW.md` (REFERENCE, iter 322fa).

## Tech stack at a glance

| Layer | Tech | Version pinned by |
|---|---|---|
| Frontend | React 19 (CRA) + Tailwind + shadcn/ui + lucide-react + Motion | `frontend/package.json` |
| Backend  | FastAPI + Uvicorn + Motor (async Mongo) | `backend/requirements.txt` |
| Database | MongoDB 6 (Atlas in prod, local in preview) | `MONGO_URL` |
| LLM      | OpenRouter (free-tier ladder) + Claude / GPT / Gemini BYOK + Emergent LLM key | `services/dev_cto_chat.py` |
| Auth     | JWT HS256 + bcrypt + EMERGENCY_RESET_SECRET emergency one-shot | `routers/auth_router.py`, `routers/emergency_reset_router.py` |
| Hosting  | Hetzner FSN1 (Helsinki) for backend; Cloudflare in front | `aurem.live` |
| CI / IDE | Emergent platform (preview) → Save-to-GitHub → Deploy | platform |

## Frontend

- **Stack**: React 19 functional components, hooks only.
- **Bundler**: CRA (`yarn start` / `yarn build`).
- **Styling**: Tailwind utility classes + 1 small custom CSS file per
  surface (e.g. `DevCtoChatPanel.mobile.css`, `.animations.css`).
- **State**: React state only (no Redux). Cross-component messages use
  `window.dispatchEvent(new CustomEvent(...))` — see
  `VerificationBadge.jsx` + `aurem-verify-event`.
- **Routing**: React Router (declared in `App.js`).
- **API client**: `fetch` + `process.env.REACT_APP_BACKEND_URL`.
- **Auth tokens**: localStorage (`aurem.dev_jwt`, `aurem.admin_jwt`),
  attached via `devAuthHeaders()` helper in `DeveloperShell.jsx`.
- **Icons**: `lucide-react` ONLY (no emoji icons).
- **Toasts**: `sonner` (shadcn pattern).
- **Mobile**: dedicated CSS files behind `@media (max-width: 768px)`.

## Backend

- **Framework**: FastAPI, Uvicorn worker. Hot reload in preview.
- **Async DB**: Motor (Mongo async driver).
- **Router registry**: `routers/registry.py` includes EVERY router
  individually so new files (cto_tools / cto_verify / cto_learning /
  cto_codebase / resend_webhook / etc.) all land through the same
  guarded `try` blocks.
- **Schedulers**: APScheduler — Ghost Scout, auto-blast engine,
  Sentinel diagnostics, cto_learning weekly review (Sun 02:00 UTC).
- **Audit log**: `unified_audit_log` collection. Every external touch
  (LLM call, email send, webhook, admin login) writes one row.
- **Error handling**: No silent failures. Errors land in
  `unified_audit_log` + `WatchFiles`-detected reloads in the dev
  log + the failure surface in ORA chat.

### Critical backend rules (do not violate)

1. **All API routes prefixed `/api`** — Kubernetes ingress + nginx
   redirect counts on this.
2. **All URLs / secrets from `.env`** — never hardcode.
3. **Mongo `_id` MUST be excluded** in every projection that returns
   to the wire. Use `{"_id": 0}` or pydantic models.
4. **Datetime**: `datetime.now(timezone.utc)`. Store as ISO string OR
   native dt — be consistent in any single collection.
5. **bcrypt rounds = 12** for user passwords.
6. **Admin JWT bypass** in `_current_dev()` reads `is_admin` /
   `is_super_admin` flags; the auto-bootstrap path may return rows
   without these flags so always re-check via the JWT itself when
   gating admin endpoints (see D-49a fix in `cto_tools_router.py`).

## Authentication + sessions

- **Customer**: email + 6-digit OTP (resent via Resend).
- **Admin / Founder**: email + password (bcrypt, rounds 12).
- **Developer**: signup → email verify → JWT (HS256).
- **Enterprise**: SAML SSO (signed AuthnRequest) + SCIM.
- **Emergency reset**: `EMERGENCY_RESET_SECRET` enables a one-shot
  POST that rotates the admin password without console access.
- **JWT secret rotation**: invalidates every session — must be planned
  with a maintenance window.

## APIs (live surface)

The full list is in `SPEC_03_APP_FLOW.md` mapped to UI screens. Key
endpoint families:

- `/api/auth/*` — login, signup, OTP, password reset.
- `/api/admin/*` — security keys, founder customers, blast control.
- `/api/developers/*` — portal, BYOK, GitHub OAuth, save-to-github.
- `/api/developers/cto/*` — chat stream, tools, verify, learning,
  codebase / file / github commits.
- `/api/leads/webhook/resend` + `/api/webhooks/resend` — Resend events.
- `/api/cto/leads/hot` — hot-lead surfacing.
- `/api/ora/*` — ORA customer agent.
- `/api/blast-chain/*` — multi-channel blast control.
- `/api/version` — iter + commit SHA + build at — cache-bust badge.
- `/api/enterprise/*` — branding, SSO, SCIM, audit, residency.

## LLM orchestration

- **Free-tier ladder** — OpenRouter DeepSeek / Llama / Mixtral fallback
  for cheap turns.
- **BYOK** — Anthropic, OpenAI, Gemini routes (per provider URL +
  model).
- **Emergent LLM key** — universal key for Claude / Gemini / GPT /
  Sora 2 / Whisper (free turns allotment).
- **Temperature (D-57)**:
  - Code intents → 0.0 (deterministic)
  - Planning intents → 0.2
  - Default → 0.1
- **Guardrail (D-57)** — system message banning invented SHAs / dates /
  iter tags / endpoints injected on every turn.
- **Context injectors**:
  - `_maybe_inject_codebase` — `/file <path>` and "line N of X"
    detection → real bytes from `/app/...` (D-54).
  - `_maybe_inject_web_search` — Tavily for "search ..." prefix.

## Third-party integrations

| Service | Where the keys live | Purpose |
|---|---|---|
| Resend            | `RESEND_API_KEY`     | Email send + webhook events. |
| Twilio            | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_WA_FROM_NUMBER` | SMS + WhatsApp Business. |
| WHAPI.cloud       | `WHAPI_API_TOKEN` + `WHAPI_BLAST_DISABLED` | WhatsApp primary; falls through to Twilio WABA when disabled (D-57). |
| Stripe            | `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` | Billing. |
| OpenRouter        | `OPENROUTER_API_KEY` | Cheap LLM ladder. |
| Emergent LLM key  | `EMERGENT_LLM_KEY`   | Universal premium LLM access. |
| Tavily            | `TAVILY_API_KEY`     | Live web search inside CTO chat. |
| iProyal           | `IPROYAL_PROXY_URL`  | Geo-rotating proxy for OSM scrape. |
| GitHub OAuth      | `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` | D-42 Save-to-GitHub. |
| Hetzner Cloud API | `HETZNER_API_TOKEN`  | Pending — Real SSH deploy. |
| Telegram          | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Legion command approvals. |

## Infrastructure / deployment

- **Preview** — current Emergent-managed Kubernetes pod
  (`*.preview.emergentagent.com`). Hot reload, full MongoDB local.
- **Production** — `aurem.live` running on Hetzner FSN1; Cloudflare in
  front for caching + WAF. Direct Emergent deploy (preview → prod) —
  the deploy step does NOT push to GitHub, which is why D-54's
  GitHub-read code requires a separate "Save to GitHub" step.

## Security baseline

- All endpoints `Authorization: Bearer <JWT>` except `/api/health`,
  `/api/version`, public landing.
- Path traversal protection on `/api/developers/cto/file*` — sandbox
  rooted at `/app`, blocklist for `.env`, `.git/`, `*.pem`, `*.key`,
  `node_modules/`, `__pycache__/` (D-54).
- CORS allow-list: `CORS_ORIGINS=https://aurem.live,https://www.aurem.live`
  + preview default.
- bcrypt cost = 12. Argon2 not yet used (planned).
- AUREM_ENCRYPTION_KEY = base64 32-byte AES-256-GCM key for at-rest
  secrets in `customer_security_keys`.
- Telegram alerts on HIGH-risk Legion commands.

## Performance + reliability targets

- API p50 < 250 ms (preview), < 500 ms (prod).
- LLM stream first-token < 1.5 s on free tier, < 800 ms on BYOK.
- Auto-blast cycle < 60 s for 50 leads.
- 99.5 % uptime on `aurem.live`.
- pytest suite < 12 s for the active D-40b → D-57 ring (166 tests).

## Testing strategy

- pytest at `/app/backend/tests/test_*_d<N>.py`.
- Static-asset assertions for frontend wiring (e.g.
  `test_push_deploy_d51.py` greps the JSX for required testids).
- Service-level tests use in-memory `_Coll` stubs so motor never hits
  Mongo during CI.
- Live E2E via curl against `REACT_APP_BACKEND_URL` after every iter.
