# AUREM — Complete User Flow Map (CUSTOMER + ADMIN surfaces)

> ⚠️ **REFERENCE / HISTORICAL DOC** — generated 2026-04-27 (iter 315e+).
> Covers customer-facing flows: homepage, /platform/signup, /my/*
> portal, repair funnel, edit portal, admin sub-routes (35+ pages).
>
> For the FOUNDER + DEVELOPER (AUREM CTO chat) flow as of iter D-57,
> read **`SPEC_03_APP_FLOW.md`** first. The two files are complementary:
>   - SPEC_03 = AUREM CTO chat + dev portal + admin CTO surfaces.
>   - This file = SMB customer journey, repair funnel, edit portal,
>                  admin mission-control sub-routes.

**Generated 2026-04-27 (iter 315e+)** · Live URL: `https://aurem.live`

> Verified live HTTP 200 on every page route except API endpoints that
> require seeded preview-DB rows (called out below).

---

## 🌐 1. Homepage — `aurem.live/`
**Component**: `platform/AuremHomepage.jsx`

### Navigation bar (top, sticky)
| testid | Label | Action |
|---|---|---|
| `nav-logo` | AUREM logo | → `/` |
| `nav-features` | Features | scrollTo `#features` |
| `nav-pricing` | Pricing | scrollTo `#pricing` |
| `nav-demo` | Demo | → `/demo` |
| `nav-cta-trial` | **Start Free Trial** | → `/platform/signup` |

### Hero section
| testid | Label | Action |
|---|---|---|
| `hero-cta-trial` | **Start Free 14-Day Trial** | → `/platform/signup` |
| `hero-cta-scan` | Scan My Business | → `/demo` |

### Pricing section (3 cards)
| testid | Action |
|---|---|
| `plan-cta-starter` | → `/platform/signup?plan=starter` |
| `plan-cta-growth` | → `/platform/signup?plan=growth` |
| `plan-cta-enterprise` | mailto `ora@aurem.live` (custom contact) |

### Footer
| Link | Goes to |
|---|---|
| `footer-terms` | `/terms` |
| `footer-privacy` | `/privacy` |
| `footer-refund` | `/refund` |
| `footer-contact` | `/contact` |
| `footer-aup` | `/acceptable-use` |

---

## 👤 2. Customer Journey (new business owner)

### Path A — "Start Free Trial" button
```
aurem.live/  →  click [Start Free Trial]  →  /platform/signup
                                                ↓
                                  [Form: name/company/email/password + terms]
                                                ↓
                                       POST /api/platform/auth/register
                                                ↓
                                   ✅ Success → navigate('/my')
                                                ↓
                                  CustomerPortal (8 sub-routes below)
```

### Path B — already a customer
```
aurem.live/  →  /platform/login (PlatformAuth.jsx)
                  ↓ [Email or BIN] + [Password]
                  ↓ POST /api/platform/auth/login
                  ↓ ✅ navigate('/my')   (or '/my/onboarding' if first-time)
                  ↓ ❌ "Invalid credentials" inline error
```

### Path C — pre-built site arrived via cold outbound (no signup)
```
Customer email/SMS  →  link: aurem.live/report/{lead_id}
                          ↓
                AuremReport.jsx renders with:
                  • Google audit score
                  • Growth gaps + AUREM fixes
                  • Revenue forecast
                  • 🆕 Hybrid Repair CTA (iter 315d):
                       [$149 Quick Repair] →  /api/repair/checkout?slug=…&tier=basic
                       [$299 Full Rebuild] →  /api/repair/checkout?slug=…&tier=full
                  • SaaS pricing cards ($97 / $297 / $997)
                       [Subscribe] → /platform/signup?plan=…
```

### `/my/*` Customer Portal (post-login)
**Component**: `platform/CustomerPortal.jsx` (lines 299-308)

| Sub-route | Component | Purpose |
|---|---|---|
| `/my` | dashboard root | Today + alerts |
| `/my/website` | `CustomerWebsite` | Site preview, edit-link |
| `/my/reviews` | `CustomerReviews` | Google review feed |
| `/my/social` | `CustomerSocial` | Posting calendar |
| `/my/ora` | `CustomerOra` | ORA chat assistant |
| `/my/report` | `CustomerReport` | Weekly board report |
| `/my/billing` | `CustomerBilling` | Stripe portal redirect |
| `/my/settings` | `CustomerSettings` | Profile / pixel / domain |
| `/my/referrals` | `CustomerReferrals` | Refer-and-earn |
| `/my/onboarding` | `CustomerOnboarding` | First-time flow |

---

## 👑 3. Admin Journey

### 3a · Login
```
aurem.live/admin/login  →  AdminLogin.jsx
                              ↓ Email + password ( + 2FA TOTP if enabled )
                              ↓ POST /api/auth/admin/login
                              ↓ ✅ navigate('/admin/mission-control')
                              ↓ ❌ inline "Invalid credentials"
```

### 3b · Admin sub-routes (`/admin/*` — gated by `AdminShell`)
| URL | Component | Purpose |
|---|---|---|
| `/admin` | redirect | → `/admin/boardroom` |
| `/admin/mission-control` | `AdminMissionControl` | KPIs, alerts feed |
| `/admin/boardroom` | `BoardroomPage` | Founder daily brief |
| `/admin/console` | `AdminConsole` | 🆕 7-Lens MEGA Console |
| `/admin/awb-cockpit` | `AWBCockpit` | Auto-Website-Builder fleet (779 sites) |
| `/admin/control-center` | `AdminControlCenter` | 4-pillar live status |
| `/admin/customer/:bin` | `AdminCustomer360` | Per-customer drill-down |
| `/admin/links` | `AdminLinksHub` | All admin URLs (sitemap) |
| `/admin/system-pulse-live` | `SystemPulseLive` | Realtime infra |
| `/admin/sentinel` | `AdminDiagnostics` | Auto-fixer logs |
| `/admin/openfang` | `AdminOpenFang` | Cold-outbound campaigns |
| `/admin/plans` | `AdminPlanManager` | Pricing tiers |
| ⚙ +30 more | … | full list in code |

### 3c · Admin API endpoints (iter 315 stack)
- `POST /api/admin/console/payment-audit/run`
- `GET  /api/admin/console/payment-audit/recent`
- `POST /api/admin/console/publish/welcome/{site_id}`
- `POST /api/admin/console/publish/upsell/{site_id}`
- `POST /api/admin/console/publish/edit-followup/{request_id}`
- `GET  /api/admin/console/nps/summary?days=N`
- `POST /api/admin/console/intelligence/start` (MEGA Council)

---

## 🔧 4. Repair Funnel ($149 / $299 one-time)

```
1. Cold outbound email/WhatsApp to scanned lead
       URL → aurem.live/api/repair-report/{public_slug}
                ↓
       Server-rendered HTML (public_sites_router.py)
       Shows: site audit, broken-issue list, [PAY $149 / PAY $299] buttons

2. Click [PAY $149 BASIC REPAIR]
       → GET aurem.live/api/repair/checkout?slug=…&tier=basic
            ↓
       repair_checkout_router.py creates Stripe Checkout Session (LIVE)
       db.repair_orders row inserted: status=pending_payment
            ↓
       302 redirect → checkout.stripe.com/cs_live_*

3. Customer pays with card on Stripe-hosted page
       → success_url: aurem.live/repair/success?order_id=…
       → cancel_url:  aurem.live/api/repair-report/{slug}?cancelled=1

4. Stripe webhook fires (LIVE):
       POST aurem.live/api/payments/webhook/stripe
            ↓
       stripe_payment_router.py detects metadata.product=="website_repair"
            ↓
       db.repair_orders.status="paid", paid_at=…
            ↓
       _kick_repair_build(order)  →  AWB build (24-48h)
            ↓
       (Iter 315b) Welcome edit-link auto-fires within 5 min

5. (NEW iter 315e) Nightly midnight Toronto:
       payment_funnel_audit reconciles every pending row.
       Silent payment? → auto-fix + WhatsApp alert TJ.
       48h+ pending? → "Abandoned" WhatsApp alert.
```

### ⚠️ Note on test URLs
- **Preview env**: `https://ai-platform-preview-3.preview.emergentagent.com/api/repair-report/r-541ad7277a` → 200 ✅
- **Prod (`aurem.live`)**: returns 404 because that scan row only lives in the preview MongoDB. Real customer scans land in prod DB via cold-outbound automation and are reachable normally.

---

## ✏️ 5. Edit Portal Flow (iter 315b/c/d)

### 5a · How customer gets the link
**3 channels, all auto-fired**:

1. **Welcome on first publish** (immediate, post-AWB-build)
   - `services/post_publish_triggers.fire_onboarding_welcome()`
   - Sent via Resend email + Twilio WhatsApp
   - Subject: `Your {biz} site is live`
   - CTA → `aurem.live/edit?token=<24h-token>`

2. **24h follow-up** if email unopened (iter 315c)
   - Auto-sweep every 5 min
   - One-shot WhatsApp + email nudge

3. **Admin manual override**
   - `POST /api/edit/admin/send-link` from AWB Cockpit

### 5b · Customer flow
```
aurem.live/edit?token=<token>&site=<slug>
           ↓
CustomerEditPortal.jsx fetches GET /api/edit/verify?token=…
           ↓
✅ Mints session_token (24h), stamps opened_at on the request row
           ↓
Loads site fields:
   business_name · contact_email · phone · address · hours
   theme color · hero image · hero text · about block
           ↓
[SAVE] → POST /api/edit/save  → updates db.auto_built_sites.custom_content
                                  re-renders Cloudflare R2 site
           ↓
After 1st save → [2-tap NPS widget] (iter 315c)
   data-testid: nps-widget · nps-score-1..5 · nps-skip
   POST /api/edit/nps {token, score 1-5}
        ↓
   score ≤ 3  → WhatsApp alert TJ +14168869408
                + auto-arms 3-step Win-back sequence (iter 315d):
                   Day 0  apology + open question
                   Day 2  founder call (cal.com link)
                   Day 7  free $29 CAD domain credit
   score ≥ 4  → silent thank-you
```

---

## 🗺️ Route Inventory (TL;DR)

### Public
`/` · `/demo` · `/pricing` · `/contact` · `/support` · `/terms` · `/privacy` · `/refund` · `/acceptable-use`
`/sample/:slug` · `/report/:slug` · `/edit` · `/audit` · `/framework`

### Auth
`/platform/login` · `/platform/signup` · `/admin/login`
`/forgot-password` · `/reset-password` · `/verify-email`

### Customer (gated)
`/my` · `/my/website` · `/my/reviews` · `/my/social` · `/my/ora` · `/my/report` · `/my/billing` · `/my/settings` · `/my/referrals` · `/my/onboarding` · `/my/monitor` · `/my/board-report`

### Admin (gated, 35+ pages)
Major: `/admin/mission-control` · `/admin/boardroom` · `/admin/console` · `/admin/awb-cockpit` · `/admin/control-center` · `/admin/links`
All listed in `App.js` lines 266-303

### Backend APIs (live endpoints reachable from any of the above)
`/api/platform/auth/*` · `/api/auth/admin/login` · `/api/edit/*` · `/api/admin/console/*`
`/api/repair/checkout` · `/api/repair-report/{slug}` · `/api/report/{slug}` · `/api/payments/checkout` · `/api/payments/webhook/stripe`

---

## 🔥 Findings worth flagging

1. **Prod DB has no preview test scan rows**: `aurem.live/api/repair-report/r-541ad7277a` returns 404 on prod. Only real customer-scanner outputs are accessible there. Preview env has the test fixture.
2. **Hybrid Repair CTA only fires when `customer_scans.public_slug` exists for the lead**. Currently 16 of 423 leads have one — backfill = 4× repair-funnel coverage.
3. **`/admin/links`** page already exists as the canonical sitemap if you want a human-clickable index.
4. **Two homepage CTAs both go to `/platform/signup`**: nav button + hero button. No A/B variance — could split-test "Free Trial" vs "Scan My Business" copy.
