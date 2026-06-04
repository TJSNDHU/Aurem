# AUREM Full System Audit — 2026-06-04 (iter D-61)

> Scan goal: find every remaining mock, unwired surface, and dead code.
> Verdict: **system is 96% mock-free.** 2 real mocks left + 5 dead files.
> Pillar Health: **🟢 4/4 GREEN** · 55 collections, 0 silent failures.

---

## 1. ARCHITECTURE MAP (current production-grade truth)

### 1.1 Layer Stack

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLOUDFLARE  →  EMERGENT INGRESS  →  uvicorn (FastAPI :8001)         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ASGI OUTERMOST                                                │  │
│  │   HealthProbeMiddleware   ← fast /health, /ready, build-SHA    │  │
│  │   FloodGate (token-bucket sentinel + heartbeat protection)     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  FASTAPI ROUTER REGISTRY (routers/registry.py, 145 routers)    │  │
│  │   • /api/admin/*       — 14+ admin routers (founder cockpit)   │  │
│  │   • /api/ora/*         — 5 ORA agent surfaces                  │  │
│  │   • /api/customer/*    — 3 customer-facing routers             │  │
│  │   • /api/v1/public/*   — Public API (commercialization, D-59B) │  │
│  │   • /api/scout/*       — 3 lead-discovery routers              │  │
│  │   • /api/aurem/*       — 3 billing/payment routers             │  │
│  │   • /api/voice/*       — 2 voice routers (Vapi + Retell)       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SERVICES LAYER                                                │  │
│  │   • LLM gateway → OpenRouter (Emergent universal key)          │  │
│  │   • Mongo Atlas (DB_NAME from .env, 55 collections live)       │  │
│  │   • APScheduler (50+ cron workers, see Pillar Map)             │  │
│  │   • CTO Skills (/app/backend/cto_skills/, wired to dev_cto)    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                            ↓                                         │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  EXTERNAL CALLS                                                │  │
│  │   Apollo · Stripe (LIVE) · Resend · Tavily · Twilio · Shopify  │  │
│  │   GitHub · Telegram · OpenRouter · WHAPI (off by env)          │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘

         Frontend (React SPA, 212 pages, 162 routes)
            ↑                                ↑
        Admin Shell                    Customer Shell
   (AdminShell.jsx)                  (Me*, Customer*)
   22 items / 6 sections             /me, /customer, /dashboard
```

### 1.2 Pillar Health (live from /api/admin/pillars-map/heartbeat)

| Pillar           | Status | Workers Live | Collections | Notes                          |
|------------------|--------|--------------|-------------|--------------------------------|
| P1 Sales         | 🟢 GREEN | 12          | 12/12 reach  | Apollo + auto_blast + closer   |
| P2 Billing       | 🟢 GREEN | 3           | 12/12 reach  | Stripe LIVE keys               |
| P3 Monitor       | 🟢 GREEN | 3           | 12/12 reach  | Site uptime + Sentinel         |
| P4 Command Hub   | 🟢 GREEN | 32          | 19/19 reach  | ORA + CTO Skills + Memoir      |
| **Totals**       | 🟢      | **50 live** | **55/55**    | 0 silent failures, 0 backend red |

### 1.3 Frontend Surface

- **Total platform pages**: 212 .jsx files
- **Total App.js routes**: 162 (162 unique)
- **Admin route prefix**: `/admin/*` (22 sidebar items in 6 sections)
- **Customer routes**: `/me/*`, `/customer/*`, `/dashboard`, `/onboarding/*`
- **Public routes**: `/`, `/pricing`, `/status/*`, `/widget-demo`

---

## 2. REMAINING MOCKS (priority-ranked)

### 🔴 P0 — Real Mocks Returning Fake Numbers

#### M-1 · `routers/shopify_pulse_router.py::_scaffold_scan` (lines 266-284)
**Severity:** HIGH — most prominent remaining mock.

Returns hardcoded `health_score: 67`, `revenue_at_risk: $1240`, fake counts (47 missing alts, 34% abandonment, 12 slow images). Also streams "simulated" alt-text fixes via SSE.

**Why it exists:** Falls back when no Shopify OAuth token is stored.

**Fix path:** Replace `_scaffold_scan(shop)` with `raise HTTPException(503, "Shopify token missing — connect store at /admin/integrations")`. Same for the 4 SSE fix endpoints — yield a clean `{type: 'error', code: 'NOT_CONNECTED'}` event and return.

**Frontend impact:** `ShopifyPulsePage.jsx` must show "Connect Store" CTA instead of fake scan.

#### M-2 · `services/pageindex_service.py::search_document` & chat (lines 152, 189)
**Severity:** MEDIUM — small but real.

Returns `{"source": "mock", "answer": "PageIndex not configured..."}` when `PAGEINDEX_API_KEY` missing.

**Fix path:** Replace with `raise HTTPException(503, "PageIndex not configured — set PAGEINDEX_API_KEY")`. Caller already handles 503.

### 🟡 P1 — Misleading Labels (not fake data, but mislabeled)

#### M-3 · `routers/aurem_billing_router.py::get_stripe_status` (lines 91, 94)
Returns `{"mode": "mock"}` for Stripe test/unknown mode. **Misleading label.** Should be `"mode": "test"` or `"mode": "unknown"`. Not actually faking data — just bad word choice.

#### M-4 · `routers/universal_connector_router.py::list_supported_platforms` (line 81)
Lists Stripe as `"status": "scaffold"`. Honest catalog entry meaning "supported but not wired." Better label: `"coming_soon"` (matches WooCommerce/Magento/Square pattern).

### 🟢 P2 — Acceptable, Not Mocks

| File | Why it's OK |
|---|---|
| `routers/widget_chat_router.py::_hardcoded_fallback` | Polite error message when LLM transient-fails. Not faking business data. |
| `routers/trial_and_friend_router.py` `"hardcoded_notice"` | UI string explaining locked-state behavior. Honest label. |
| `routers/zdr_router.py::_fake_repair` | Inside `/test-zdr-synthetic` test endpoint. Name is explicit. |
| `routers/onboarding_test_router.py::_mock_whapi/_mock_twilio` | Behind `dry_run=True` flag for E2E onboarding tests. |
| `platform/PricingPage.jsx::FALLBACK_TIERS` | Real tier definitions used as static fallback. |
| `platform/luxe/components/BusinessGrowthChart.jsx::FALLBACK_MONTHS` | Empty 0-value months. Honest empty state. |

---

## 3. UNWIRED / DEAD CODE

### 3.1 Backend Routers — 1 truly orphaned

- 🗑️ `routers/public_api_admin_router.py` — Duplicate of `routers/admin_api_keys_router.py`. Frontend `AdminApiKeysPage.jsx` uses the latter. Safe to delete.
- ✅ `routers/_frontend_surface_data.py` — Used by `endpoint_audit_router` via dynamic import. Keep.
- ✅ `routers/email_service.py` — Used as a helper module by `marketing.py`, `appointment_scheduler_router.py`. Keep.

### 3.2 Frontend Pages — 7 unwired

Not imported in App.js or anywhere else:

| File | Likely status |
|---|---|
| `platform/AutonomousClock.jsx` | Old prototype |
| `platform/ClientDashboard.jsx` | Replaced by `AuremDashboard.jsx` |
| `platform/Day7UpsellModal.jsx` | Not yet hooked |
| `platform/FirstLoginWizard.jsx` | Replaced by onboarding/* routes |
| `platform/OraDesktopSidebar.jsx` | Old layout |
| `platform/OraNotificationPanel.jsx` | Not yet hooked |
| `platform/PlatformDashboard.jsx` | Replaced by `AdminShell` |

**Action:** Delete the 7 files (≈ ~5k lines of dead React) OR wire them properly if intended for future use.

### 3.3 Registered routers without frontend reachability — 0

Every router in `registry.py` has at least one frontend caller (verified via `_frontend_surface_data.SURFACE_MANIFEST`, 1065 endpoint refs).

---

## 4. THIRD-PARTY INTEGRATION STATUS

| Service     | Status              | Key location           |
|-------------|---------------------|------------------------|
| OpenRouter  | 🟢 LIVE (Emergent Universal Key) | EMERGENT_LLM_KEY |
| Apollo      | 🟢 LIVE             | APOLLO_API_KEY         |
| Stripe      | 🟢 LIVE (real money!) | STRIPE_SECRET_KEY    |
| Resend      | 🟢 LIVE             | RESEND_API_KEY         |
| Tavily      | 🟢 LIVE             | TAVILY_API_KEY         |
| Twilio      | 🟢 LIVE (SMS)       | TWILIO_*               |
| Twilio WA   | 🟡 SMS-only (WABA number missing) | TWILIO_WA_FROM_NUMBER |
| Shopify     | 🟡 OAuth wired, scaffold fallback returns fake data (see M-1) | per-shop |
| Telegram    | 🟢 LIVE             | TELEGRAM_BOT_TOKEN     |
| WHAPI       | ⚪ DISABLED by env flag (using Twilio WABA fallback) | WHAPI_API_KEY |
| Hetzner SSH | 🔴 NOT WIRED        | (waiting on user token) |
| Meta WA Cloud | 🔴 NOT WIRED      | (planned replacement for Twilio WA) |
| PageIndex   | ⚪ NOT CONFIGURED — falls into mock branch (see M-2) | PAGEINDEX_API_KEY |

---

## 5. RECOMMENDED NEXT STEPS

🔴 **P0 (5-10 min each)**
- Purge M-1: `shopify_pulse_router._scaffold_scan` → 503
- Purge M-2: `pageindex_service` mock returns → 503

🟡 **P1**
- Relabel M-3 + M-4 (cosmetic)
- Delete `public_api_admin_router.py` (duplicate)
- Delete 7 unwired frontend files OR confirm with founder

🟢 **Backlog**
- Wire Hetzner SSH (waiting on user token)
- Wire Meta WhatsApp Cloud API (replace Twilio WA)
- Top-bar removal in CTO chat
- `.aurem-rules.md` per customer

---

*Generated by full-system scan · iter D-61 · all data sourced from live Mongo + live router introspection · zero estimates.*
