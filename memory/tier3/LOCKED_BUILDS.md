# 🔒 AUREM LOCKED BUILDS — DO NOT ROLLBACK

**Date Locked:** Feb 20, 2026 — Iteration 256
**Enforcement:** `/app/backend/tests/test_locked_builds.py` (pytest regression suite)
              + `/app/backend/services/lock_in_validator.py` (startup log validator)

This is the **contract** between the platform and future agents. Every build
listed here is **production revenue-critical** and must remain operational.
If any item here regresses, the platform silently loses paying customers.

---

## 🎙️ Retell AI Voice Agent — LOCKED
- **Router:** `/app/backend/routers/voice_agent_router.py`
- **Key:** `RETELL_API_KEY` in `/app/backend/.env`
- **Endpoints:** `/api/admin/voice-agent/retell/{status,voices,agents,phone-numbers}`, `/api/retell/webhook` (HMAC-SHA256 verified), `/api/admin/voice-agent/config/{bin}`
- **Critical:** Uses 2-step flow `create-retell-llm` → `create-agent` (NEVER revert to single-step). HMAC signature verification is MANDATORY.
- **Revenue:** $149/mo Voice Agent add-on

## 💳 Stripe Annual Pricing — LOCKED
- **Env vars:** `STRIPE_PRICE_STARTER_ANNUAL`, `STRIPE_PRICE_GROWTH_ANNUAL`, `STRIPE_PRICE_ENTERPRISE_ANNUAL`
- **Values:** CAD 970 / 2970 / 9970 per year (= 10× monthly = 2 months free)
- **Backend:** `stripe_embed_router.py` auto-selects annual when `annual: true` flag sent
- **Frontend:** `PricingPage.jsx` monthly/annual toggle
- **Revenue:** 30-40% higher ARR + lower churn

## 🔍 SEO Audit $49 SKU — LOCKED
- **Router:** `/app/backend/routers/seo_audit_router.py`
- **Frontend:** `/app/frontend/src/platform/SEOAuditPage.jsx` at route `/audit`
- **Stripe product:** auto-created on startup via `ensure_stripe_product()` (lookup_key `aurem_seo_audit_49_cad`)
- **Pipeline:** PageSpeed + Firecrawl + Places → grade + 20 issues
- **Webhook:** Stripe `checkout.session.completed` with metadata `product=seo_audit_49` → calls `mark_paid(session_id)`
- **Revenue:** $49 CAD one-time per audit

## 📰 Daily Intel Engine — LOCKED
- **Router:** `/app/backend/routers/daily_intel_router.py`
- **Key:** `TAVILY_API_KEY`, `RESEND_API_KEY`
- **CASL:** **Double opt-in MANDATORY** — `consent_daily_digest: false` must return HTTP 400
- **Endpoints:** `/api/daily-intel/{subscribe,confirm,status,unsubscribe}`
- **Batch function:** `run_daily_intel_batch()` — wire to scheduler for 7 AM daily cron
- **Revenue:** $29/mo (Growth tier bundle + standalone)

## 🇨🇦 Sovereign Privacy Mode — LOCKED
- **Router:** `/app/backend/routers/privacy_mode_router.py`
- **Key:** `SOVEREIGN_NODE_URL` → `sovereign.aurem.live` (Llama 3.1)
- **Endpoints:** `GET/PATCH /api/customer/privacy`
- **Exported helper:** `is_sovereign_enabled(db, email)` — services MUST call this before LLM dispatch
- **Gating:** Requires active `sovereign_privacy` subscription (HTTP 402 if not subscribed)
- **Revenue:** $49/mo add-on (clinic/legal/finance verticals)

## 📞 Lead Enrichment + CASL — LOCKED
- **Service:** `/app/backend/services/lead_enrichment_casl.py`
- **Keys:** `NUMVERIFY_API_KEY`, `IPSTACK_API_KEY`
- **Helpers:** `enrich_lead(phone, ip)`, `casl_compliant(consent_sms, consent_email, channel)`
- **Public lead router:** `public_lead_router.py` now accepts `phone`, `consent_email`, `consent_sms`
- **CASL:** `casl_compliant` MUST gate all SMS/voice triggers

## 📧 SendGrid → Resend Compat Shim — LOCKED
- **Shim:** `/app/backend/services/sendgrid_compat.py`
- **Modern wrapper:** `/app/backend/services/email_service_resend.py`
- **9 migrated files (DO NOT revert imports):**
  1. `routes/abandoned_cart_automation.py`
  2. `routes/reroots_p0_fixes.py`
  3. `routes/loyalty_bonuses.py` (uses `sendgrid_send_email` from reroots)
  4. `routes/automation_gaps.py`
  5. `routes/reviews_module.py` (uses `sendgrid_send_email` from reroots)
  6. `routes/automations.py`
  7. `routes/waitlist_restock.py`
  8. `services/customer_service.py`
  9. `services/refund_service.py`
- **All imports must read:** `from services.sendgrid_compat import SendGridAPIClient, Mail` (NEVER `from sendgrid import`).

## 🛒 Shopify OAuth 1-Click — LOCKED
- **Router:** `/app/backend/routers/shopify_oauth_router.py`
- **Keys:** `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_SCOPES`
- **Endpoint:** `/api/shopify/auth?shop=xxx.myshopify.com` → redirects 302/307 to Shopify OAuth
- **Frontend:** `ShopifyAppManager.jsx` (5 tabs) + card in `PlatformDashboard.jsx` Tools tab

## 🔐 Google OAuth (Emergent-managed) — LOCKED
- **Backend:** `/app/backend/routers/google_oauth_callback.py`
- **Frontend:** `/app/frontend/src/components/GoogleAuthButton.js` (Emergent redirect flow)
- **Callback:** `/app/frontend/src/platform/GoogleAuthCallback.jsx` (reads `#session_id=` fragment)
- **Flow:** User clicks → redirect to `auth.emergentagent.com` → back with fragment → POST `/api/auth/google/callback` → JWT
- **No Google Cloud keys needed.**

## 🔌 WordPress Plugin — LOCKED
- **Artifact:** `/app/backend/static/plugins/aurem-pixel.zip` (4405 bytes)
- **Download endpoints:** `/api/plugins/wordpress` (friendly), `/api/static/plugins/aurem-pixel.zip` (direct)
- **Frontend card:** `PlatformDashboard.jsx` Tools tab → "1-Click Installers" section
- **Plugin:** injects pixel via `wp_head`, optional Friend Scanner widget, Settings → AUREM admin page

## 📊 System Overview (Share) — LOCKED
- **Page:** `/app/frontend/src/platform/SystemOverview.jsx` (sidebar 14.10)
- **Public:** `/app/frontend/src/platform/SystemOverviewPublic.jsx` at `/share/system-overview`
- **Empire HUD map:** `/app/frontend/src/platform/FrameworkMap.jsx` at `/framework`

---

## 🗑️ ARCHIVED — DO NOT RESURRECT

These 14 files were moved to `/app/backend/_archive/` on Feb 20, 2026.
**Do not** move them back to `/routers/` or `/services/`:

**Routers (9):** clawchief_router, empire_hud_router, evolver_router, openfang_router,
sentinel_anomaly_router, sentinel_guard_router, sentinel_overwatch, sentinel_router, telegram_router

**Services (3):** sentinel_diagnose, sentinel_healer, sentinel_observer

**Tests (2):** test_iteration212_builder_evolver, test_iteration215_openfang_hmac_legion

---

## 🧪 How to verify nothing regressed

```bash
# Full regression suite
pytest /app/backend/tests/test_locked_builds.py -v

# Or individual category
pytest /app/backend/tests/test_locked_builds.py::test_retell_integration_locked -v
pytest /app/backend/tests/test_locked_builds.py::test_daily_intel_casl_enforced -v
pytest /app/backend/tests/test_locked_builds.py::test_stripe_annual_prices_env -v
```

Startup validator emits a warning banner in logs if any build is missing —
check `/var/log/supervisor/backend.err.log` on boot.

---

## For Future Agents

If you come here to remove/archive/refactor anything on this page:
1. **Do not.** These are revenue-generating production builds.
2. If you genuinely need to change something, first update this manifest in the same commit.
3. Then update `/app/backend/tests/test_locked_builds.py` to match the new contract.
4. Document the reason in `/app/memory/CHANGELOG.md`.

Each item on this page was shipped with measurable revenue impact. Touch with intention.
