# Customer Post-Login UX — Complete Interface Audit
**Date**: 2026-04-29 (iter 282d) · **Scope**: Audit only, zero code changes

---

## 🚨 Top-Level Finding

There are **TWO DIFFERENT post-login customer experiences** wired up, and they do not share state or navigation:

| Route prefix | Component | Who lands here |
|---|---|---|
| `/dashboard`, `/dashboard/*` | `AuremDashboard.jsx` (2899 lines) → role-gates to `ClientDashboard` (4 tabs) for non-admins | Homepage "Log In" button (I fixed earlier) |
| `/my`, `/my/*` | `CustomerPortal.jsx` (719 lines) → 10 sub-pages | Email magic-links, internal nav, customer welcome |

A paying customer can legitimately reach both, they look different, feel different, and expose different data. **This is the single biggest issue.** Pick ONE.

Secondary standalone customer routes also exist: `/ora`, `/edit`, `/leads`, `/alerts/panic`, `/settings/panic`, `/status/:bin` — all reachable while logged in, none linked from any customer sidebar.

---

## 1. All Post-Login Customer Routes (exhaustive)

### Primary — `/dashboard/*` (AuremDashboard shell)
**Render path**: `AuremDashboard` checks `is_admin`/`is_super_admin` from JWT.  
- If admin → **60+ tab admin shell** (not for customers, but currently reachable)  
- If NOT admin → mounts `<ClientDashboard>` inside the admin chrome

**ClientDashboard tabs (4)**:
| Tab | Content | Data source |
|---|---|---|
| `overview` | Site health score ring, scan history table, usage stats, BIN badge | `/api/client/dashboard` — **live** |
| `integrations` | Gmail, WhatsApp, Stripe, Shopify connect toggles | `/api/client/integrations` — **live** |
| `billing` | Plan info, invoices, upgrade CTA | `/api/client/billing` — **live** |
| `settings` | Notifications, API key, profile | `/api/client/settings` — **live** |

**Header elements**: Business name, Plan badge, BIN copy pill, ORA link, Run Scan button, Logout.  
**Onboarding overlay**: `OnboardingWizard` triggers if first login detected.

### Secondary — `/my/*` (CustomerPortal shell)
**Sidebar items (10) in order**:

| # | Nav label | Route | Component | Data source | State |
|---|---|---|---|---|---|
| 1 | Home | `/my` | `CustomerHome.jsx` (159L) | 2 API calls: metrics rollup | Live |
| 2 | My Website | `/my/website` | `CustomerWebsite.jsx` (752L) | 13 API calls: scans, repairs, services catalog, pixel, rescan | Live, has 3 TODOs |
| 3 | Site Monitor | `/my/monitor` | `CustomerSiteMonitor.jsx` (384L) | `/api/site-monitor/*` — uptime/incidents | Live |
| 4 | Board Report | `/my/board-report` | `CustomerBoardReport.jsx` (282L) | `/api/case-study/*` — QBR PDF generator | Live |
| 5 | Google Reviews | `/my/reviews` | `CustomerReviews.jsx` (118L) | 3 API calls: pull + auto-request | Live |
| 6 | Social Media | `/my/social` | `CustomerSocial.jsx` (109L) | 4 API calls: Postiz-backed | Live |
| 7 | ORA Chat | `/my/ora` | `CustomerOra.jsx` (385L) | `/api/aurem/chat` RAG-powered | Live, 1 TODO |
| 8 | Monthly Report | `/my/report` | `CustomerReport.jsx` (97L) | 3 API calls: auto-PDF 1st of month | Live |
| 9 | Billing | `/my/billing` | `CustomerBilling.jsx` (120L) | 3 API calls: Stripe sub + invoices + ApplePay | Live |
| 10 | Settings | `/my/settings` | `CustomerSettings.jsx` (201L) | 9 API calls: profile, notifications, password, API key, pixel | Live |

**Also mounted in AnimatedRoutes but NOT in sidebar** (orphans):
- `/my/referrals` → `CustomerReferrals.jsx` (102L) — Share BIN, earn free month
- `/my/onboarding` → `CustomerOnboarding.jsx` (332L) — Smart onboarding, **has 5 TODOs**

**Permanent top strip** on every `/my/*` page: `IdentityStrip` showing BIN · Name · Email · Company · Pixel Status pill (Online/Offline/Not Installed + "Add Pixel" button).

**Modal triggers**:
- `FirstLoginWizard` (lazy, overlay): auto-shows on `must_set_password` OR `!wizard_complete`
- `PixelInstallModal` (portal): triggered from IdentityStrip "+ Add Pixel" — snippet + Copy + Verify Install

### Standalone customer routes (NOT linked from any sidebar)
| Route | Component | Purpose | State |
|---|---|---|---|
| `/ora`, `/ora/*`, `/app` | `OraPWA.jsx` (667L) | Mobile-first PWA ORA chat with voice + file upload | Live — iter 281.9 tested |
| `/edit?token=...&site=...` | `CustomerEditPortal.jsx` (535L) | Magic-link DIY site editor for AWB-built customer sites | Live |
| `/leads` | `LeadsDashboard.jsx` (696L) | Leads Dashboard (Phase A) — originally admin, now reachable to all | Live |
| `/settings/panic` | `PanicSettings.jsx` | Panic escalation thresholds | Live |
| `/alerts/panic` | `PanicAlerts.jsx` | Panic alert log | Live |
| `/status/:bin` | `PublicStatusPage.jsx` | Public status page per BIN (unauth OK) | Live |
| `/subscriptions/custom` | `CustomSubscriptionBuilder` | Custom subscription builder | Live |

### Ambiguous / likely dead-to-customers
| Route | Component | Why dead |
|---|---|---|
| `/welcome` | `OnboardingWelcome` | Legacy onboarding, superseded by `FirstLoginWizard` |
| `/onboarding/pixel` | `OnboardingPixelStep` | Superseded by `PixelInstallModal` inside `/my/*` |
| `/sample/:slug` | `AuremSampleWebsite` | AWB-generated sample sites (pre-purchase) |
| `/graph/share/:id` | `BrainGraphShare` | Admin feature, customer won't use |
| `/demo`, `/demo/futuristic` | `Demo`, `FuturisticDemo` | Investor demo pages |

---

## 2. Navigation Flow (actual observed)

### Customer's journey after paying
1. **Purchase** → Stripe webhook → account created → welcome email with magic link
2. **Magic link lands** → `/my` (CustomerPortal) with `must_set_password=true`
3. **FirstLoginWizard modal** pops → set password → complete
4. **Auto-redirect** to `/my/onboarding` (if `!smart_onboarding_complete`)
5. **Smart onboarding** → collect URL + city → detect platform/socials/Google Places → pre-fill form → one-click start
6. **Settle at** `/my` → CustomerHome dashboard

### Customer coming back later
- Clicks "Log In" on homepage nav (I wired this earlier) → `/dashboard` → role-gate → ClientDashboard (4-tab experience)
- Or directly opens emailed link to any `/my/*` page (10-tab experience)
- **Same user, two different UIs, completely different info architecture** ← broken

---

## 3. Data State — Live vs Placeholder

### Fully live + wired (no mocks)
- ClientDashboard Overview → `/api/client/dashboard` (health score, scan history, usage)
- CustomerHome → metrics rollup
- CustomerBilling → Stripe live (3 endpoints + ApplePay)
- CustomerReviews → Google Places pull
- CustomerSocial → Postiz backend
- CustomerOra → `/api/aurem/chat` RAG
- CustomerReport → monthly PDF generator
- CustomerSiteMonitor → uptime/incidents (9 endpoints as verified earlier)
- CustomerBoardReport → QBR case-study generator
- CustomerSettings → profile/notifications/password/API-key/pixel (9 calls)
- CustomerWebsite → scans/repairs/services/pixel (13 calls) — **biggest, most active page**

### Has TODOs (incomplete but shipping)
- `CustomerOnboarding.jsx` — 5 TODOs (pre-fill detection edge cases)
- `CustomerWebsite.jsx` — 3 TODOs (service catalog filters, rescan refresh)
- `CustomerOra.jsx` — 1 TODO (session persistence refinement)

### No mocks detected — everything in the customer portal reads from real backend endpoints.

---

## 4. Broken / Empty / Ghost Sections

| Issue | Severity |
|---|---|
| **Two parallel portals (`/dashboard` vs `/my`)** — same user sees different UIs depending on entry point. Data is consistent, UX is not. | 🔴 P0 — user confusion, design debt |
| **Homepage Login button → `/dashboard`** (not `/my`). ClientDashboard has only 4 tabs; user never discovers Site Monitor, Board Report, Referrals, Reviews, Social, etc. unless they know those URLs. | 🔴 P0 — feature discoverability dead |
| **`/my/referrals`** mounted but not in sidebar → dead feature unless deep-linked | 🟠 P1 |
| **`/my/onboarding`** reachable only via auto-redirect, no way to revisit if dismissed | 🟠 P1 |
| **AuremDashboard admin chrome wraps ClientDashboard** (`PixelGateBanner` + `admin-shimmer` bg layer) → customers see faint admin aesthetic bleeding through | 🟡 P2 |
| **`/leads`, `/alerts/panic`, `/settings/panic`, `/subscriptions/custom`** all reachable post-login with no sidebar/nav entry → ghost routes | 🟡 P2 |
| **`CustomerOnboarding` has 5 TODOs** — smart detection edge cases | 🟡 P2 |
| **No global nav to `/ora` PWA** from the desktop customer portal — user has to know the URL or use the "ORA" header button in ClientDashboard (not present in CustomerPortal top strip) | 🟡 P2 |
| **No header on `/my/*`** (only sidebar + mobile hamburger) — desktop user has no way to return to homepage, check notifications, or view profile without opening sidebar | 🟡 P2 |
| **CustomerEditPortal is magic-link only** (no auth from portal) — customer can't reach their site editor from the sidebar | 🟡 P2 |

---

## 5. Navigation Flow Graph

```
HOMEPAGE (/)
 └─ [Log In] button ──→ /dashboard ──→ AuremDashboard
                                         ├─ (admin) 60-tab admin shell   ← wrong experience surface
                                         └─ (non-admin) ClientDashboard  ← 4 tabs only
                                              ├─ Overview  (health, scans)
                                              ├─ Integrations
                                              ├─ Billing
                                              └─ Settings

MAGIC LINK EMAIL ─→ /my ──→ CustomerPortal (10-item sidebar)
                             ├─ Home          → CustomerHome
                             ├─ My Website    → CustomerWebsite  (BIGGEST - 752 lines)
                             ├─ Site Monitor  → CustomerSiteMonitor
                             ├─ Board Report  → CustomerBoardReport
                             ├─ Google Reviews
                             ├─ Social Media
                             ├─ ORA Chat      → CustomerOra (inline) + also /ora (PWA)
                             ├─ Monthly Report
                             ├─ Billing
                             ├─ Settings
                             │    └─ [pixel install anchor]
                             ├─ (orphan) /my/referrals
                             └─ (orphan) /my/onboarding

ORPHAN POST-LOGIN ROUTES (reachable, unlinked):
 /ora      → OraPWA (mobile-first chat)
 /edit     → CustomerEditPortal (magic-link site editor)
 /leads    → LeadsDashboard
 /alerts/panic, /settings/panic
 /status/:bin (also public)
```

---

## 6. Component Inventory by Type

**Sidebars** (3 different ones active):
1. `CustomerPortal` own sidebar — 10 items, glass panel, floating
2. `ClientDashboard` FloatingTabRail — 4 tabs, desktop vertical + mobile bottom-dock
3. `AuremDashboard` mega-sidebar — 60+ admin items (bleeds into customer view via background)

**Top bars**:
- `/my/*`: mobile hamburger only (no desktop top bar)
- `/dashboard` → ClientDashboard: sticky top bar with business name + plan + BIN + ORA + Run Scan + Logout

**Modals / drawers / overlays**:
- `FirstLoginWizard` (lazy) — modal
- `PixelInstallModal` (portal) — modal from IdentityStrip
- `OnboardingWizard` — full-page takeover inside ClientDashboard
- `PixelGateBanner` — top banner inside `/dashboard` wrapper
- `ConnectionWizard` — sub-flow inside ClientDashboard

**Always-on floating components** (loaded by AppRouter for all routes):
- `AdminShortcuts` — **admin-only** but mounted everywhere (keyboard shortcuts for admin tools, visible effect: keystroke listeners active)
- `SystemStatusChip` — bottom-right status pill
- `ThemedToaster` — top-right toast notifications

---

## 7. What to Keep vs Rebuild (my read, for your design session)

### Keep (live, working, valuable)
- `CustomerPortal` sidebar pattern (10 items, glass aesthetic)
- `IdentityStrip` top row (BIN/name/email/company/pixel) — great consistent header
- `CustomerWebsite` (752L — the most substantive customer page, 13 endpoints, real value)
- `CustomerSiteMonitor`, `CustomerBoardReport`, `CustomerBilling` — each is a complete real feature
- `PixelInstallModal` — focused UX, recently shipped
- Magic-link `CustomerEditPortal` flow

### Rebuild / Consolidate
- **Unify `/dashboard` and `/my`** — pick one route, redirect the other. Likely `/dashboard` → redirect → `/my`. Eliminates the fork.
- **Remove AuremDashboard's role gate** for customers — ClientDashboard shouldn't live inside the admin shell (admin-shimmer bg, PixelGateBanner leak). Move to its own route or merge best bits into CustomerPortal.
- **Promote orphan routes**: add Referrals to sidebar, add re-enterable Smart Onboarding link under Settings
- **Add a desktop top bar** to `/my/*` — Home link, notifications, ORA quick-launch, profile avatar/logout
- **Demote `/leads`, `/alerts/panic`, `/settings/panic`, `/subscriptions/custom`** — either nest under Settings or hide behind admin guard

### Keep standalone (intentionally different UX surface)
- `/ora` PWA — mobile chat experience, separate codebase purpose
- `/edit` magic-link — pre-auth editor, should stay separate
- `/status/:bin` — public status page, should stay unauth-friendly

---

## 8. Endpoints Each Portal Calls (inventory for backend review)

**CustomerPortal.jsx** shell:
- `GET /api/bin-auth/customer-context`

**IdentityStrip**:
- `GET /api/customer/pixel/status` (polled 30s)
- `GET /api/customer/api-key` (on modal open)
- `POST /api/customer/api-key/regenerate` (self-heal)

**CustomerHome**: `/api/customer/home`, `/api/customer/notifications`  
**CustomerWebsite**: `/api/customer/website/*`, `/api/customer/scan`, `/api/customer/repairs`, `/api/customer/services/catalog`, `/api/customer/pixel/*`, `/api/customer/scan-friend` (13 total)  
**CustomerSiteMonitor**: `/api/site-monitor/endpoints`, `/api/site-monitor/logs`, `/api/site-monitor/incidents` (+ CRUD)  
**CustomerBoardReport**: `/api/case-study/*`  
**CustomerReviews**: `/api/customer/reviews/*`  
**CustomerSocial**: `/api/customer/social/*` (Postiz)  
**CustomerOra**: `/api/aurem/chat`  
**CustomerReport**: `/api/customer/report/*`  
**CustomerBilling**: `/api/customer/billing/*`, ApplePay init  
**CustomerSettings**: profile, notifications, password, `/api/customer/api-key`, pixel (9 calls)  
**CustomerOnboarding**: `/api/customer/smart-onboarding/*`  
**CustomerReferrals**: `/api/customer/referrals`, BIN share

**ClientDashboard** (the `/dashboard` variant):
- `GET /api/client/dashboard` — big rollup
- `POST /api/client/scan` — trigger scan
- `/api/client/integrations`, `/api/client/billing`, `/api/client/settings`

---

**End of audit. No code changed.**
