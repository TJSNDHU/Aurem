# AUREM System Mapping — Source of Truth

**Last updated**: 2026-04-24 (iter 287.7 — ORA Founder Sovereign Mode)
**Purpose**: Prevent duplicate work. Before building ANY onboarding/tour/wizard/CRM/voice feature, check here first.

---

## 🤖 ORA COMMAND CENTER (iter 287.6 – 287.7)

Universal natural-language command parser + executor across 4 channels.

### Files
- **Core**: `/app/backend/services/ora_command_center.py`
  - `parse_command(text)` — strict regex fast-path (zero-cost)
  - `_llm_intent_fallback(text, is_founder)` — Emergent LLM Key (gpt-4o-mini), ANY language
  - `execute_command(db, text, is_founder)` — orchestrator with audit log to `db.ora_command_log`
- **HTTP entry**: `/app/backend/routers/ora_command_router.py` (POST `/api/ora/command`)
- **Chat entry**: `/app/backend/routers/aurem_chat.py` Phase −1 (POST `/api/aurem/chat`)
- **Voice entry**: `/app/backend/routers/v2v_stream_engine.py` `_process_and_respond()` (WebSocket `/api/voice/stream`)

### Founder-gated intents (requires `is_admin` JWT claim)
`SYSTEM_HEALTH`, `AUTOPILOT_STATUS`, `AGENTS_STATUS`, `DEPLOY_TRIGGER`, `TENANTS_LIST`,
`REVENUE_TODAY`, `MORNING_BRIEF_NOW`, `EVENING_WRAP_NOW`, `KILL_SWITCH`, `RESURRECT`,
`INTEGRATIONS_PING`

### Languages supported
Any — English, Hindi (Devanagari + Roman Hinglish), Punjabi, Spanish, French, German,
Portuguese, Italian, Dutch, Arabic, Mandarin, Japanese, Korean, Russian, Turkish,
Vietnamese, Tagalog, Bengali, Urdu, Tamil (auto-detect, reply in same language).

---

## 🧭 ONBOARDING & TOUR SYSTEMS

### 🎯 Admin-Side (super_admin users at /dashboard)

#### 1. QuickStartWizard (task checklist on Mission Control)
- **File**: `/app/frontend/src/components/QuickStartWizard.jsx`
- **Rendered in**: `AuremDashboard.jsx` line 2648 — top of Mission Control view
- **Backend**: `/api/onboarding/status`, `/complete-step`, `/dismiss`
- **Router**: `/app/backend/routers/onboarding_router.py`
- **DB**: `db.onboarding` (per user_id)
- **Steps**:
  1. `connect_crm` → navigates to `crm-connect`
  2. `setup_pipeline` → navigates to `sales-pipeline`
  3. `activate_ora` → navigates to `ai-conversation`
- **UX**: Top card with progress bar, dismissible X button, click step → mark complete + navigate

#### 2. Invisible Coach (AI coaching sessions)
- **Backend**: `/app/backend/routers/invisible_coach.py`
- **Endpoints**: `POST /api/coach/start-invisible`, `GET /api/coach/session/{id}/transcript`
- **Purpose**: AI-led coaching sessions

---

### 🎯 Customer-Side (platform_users at /my)

#### 1. FirstLoginWizard (4-step modal)
- **File**: `/app/frontend/src/platform/FirstLoginWizard.jsx`
- **Triggered by**: `CustomerPortal.jsx` when `must_set_password=true` OR `wizard_complete=false`
- **Backend**: `/api/bin-auth/first-login/{status, set-password, wizard}`
- **Router**: `/app/backend/routers/bin_auth_router.py`
- **DB fields on `db.platform_users`**:
  - `must_set_password` (bool)
  - `onboarding_wizard_complete` (bool)
  - `onboarding_wizard_step` (int 0-3)
  - `onboarding_wizard_updated_at` (iso)
  - `onboarding_wizard_completed_at` (iso)
- **Steps**:
  1. Set Password (if `must_set_password=true`)
  2. Confirm Business Details (name, industry, city, phone)
  3. Preferences (tone, services, goals)
  4. Finish (tour intro — could be extended for Hybrid Storefront)

#### 2. CustomerOnboarding (smart form)
- **File**: `/app/frontend/src/platform/customer/CustomerOnboarding.jsx`
- **Route**: `/my/onboarding` (wired in `CustomerPortal.jsx` line 305)
- **Auto-redirect**: `CustomerPortal.jsx` line 112-117 — redirects if `!smart_onboarding_complete`
- **Backend**: `/api/smart-onboarding/{detect, start, me, health}`
- **Router**: `/app/backend/routers/smart_onboarding_router.py`
- **DB field**: `db.platform_users.smart_onboarding_complete`
- **UX flow**:
  1. Customer enters website URL + city
  2. AUREM detects platform (WordPress/Shopify/Wix/etc.), social profiles, Google Places — in parallel
  3. Pre-filled smart form for confirmation
  4. One-click → all subsystems start

#### 3. OnboardingWelcome (post-payment dashboard)
- **File**: `/app/frontend/src/platform/OnboardingWelcome.jsx`
- **Route**: `/welcome?session_id={stripe_session_id}` (wired in `App.js` line 119)
- **Backend**: `/api/onboarding/by-session/{session_id}`, `/api/onboarding/{tenant_id}`
- **Router**: `/app/backend/routers/aurem_onboarding_router.py`
- **DB**: `db.aurem_onboarding` (per tenant_id) + `db.payment_transactions`
- **UX**: ORA greeting by name, 4-step task checklist, 7-day countdown timer

#### 4. ConnectionWizard (per-client integrations)
- **File**: `/app/frontend/src/platform/ConnectionWizard.jsx`
- **Embedded as**: Tab inside ClientDashboard
- **Backend**: `/api/connector/*`
- **Router**: `/app/backend/routers/connector_router.py`
- **Purpose**: Email (Resend Pro) + WhatsApp (Twilio WABA) hybrid wiring — **WHAPI removed iter 287.4 (Meta ban)**

---

## 🤖 MASTER AUTOPILOT (iter 285.5 – 287.4)

Daily orchestrator: Scout → Verify → Hunt → Blast → Report — runs 08:00 AM Toronto.

### Files
- `/app/backend/routers/master_autopilot_router.py` — scheduler + manual `/api/autopilot/fire-now`
- `/app/backend/services/auto_blast_engine.py` — outreach sequencer (email/SMS/WhatsApp)
- `/app/backend/services/autopilot_brief_notifier.py` — `dispatch_brief()` to Resend + Telegram + Twilio
- `/app/backend/services/business_scout.py` — Google Places + DuckDuckGo + scraper
- `/app/backend/services/website_scraper.py` — DIY scraper (iter 287.0)
- `/app/backend/services/apollo_org_enrich.py` — Apollo org endpoint (iter 287.0)
- `/app/backend/services/apollo_enrichment.py` — enrichment orchestrator
- `/app/backend/services/email_guesser.py` — email guesser fallback (iter 287.2)
- `/app/backend/services/twilio_whatsapp.py` — Twilio WABA official WhatsApp (iter 287.4)
- `/app/backend/routers/deploy_trigger_router.py` — `/api/admin/deploy/trigger` fallback (iter 287.1)

### DB Collections
- `autopilot_runs` — last_run_at, scouted, hunted, blasted, status
- `campaign_leads` — {lead_id, email, phone, sources, last_blast_at, blast_count}
- `truth_logs` — audit trail of actions
- `auto_hunt_settings` — enabled, daily_limit, ramp_mode
- `agent_state` — Scout/Hunter/Closer/Envoy/Follow-up/Referral (paused, run_count)
- `system_kill_switch` — founder emergency stop
- `alerts_digest_queue` — overnight consolidated alerts (iter 286.0 digest mode)

---

### 🎯 Customer-Side (platform_users at /my) — see section 56–119 above for full wizard details.

---

## 💳 SERVICE CATALOG & PRICING (Hybrid Storefront Option C — iter 254-255)

### Frontend
- `/app/frontend/src/platform/AdminCommandHub.jsx` — unified admin hub
- `/app/frontend/src/platform/admin/PricingStudio.jsx` — 17-service editor
- `/app/frontend/src/platform/admin/VoiceAgentStudio.jsx` — Retell config
- `/app/frontend/src/platform/CustomerServicesPopup.jsx` — admin popup on ClientManager
- `/app/frontend/src/platform/customer/CustomerWebsite.jsx` — customer service grid + trial + friend scanner + pixel installer

### Backend
- `/app/backend/routers/service_catalog_router.py` — Pricing Studio APIs
- `/app/backend/routers/trial_and_friend_router.py` — Trial, friend scan, pixel install, /pricing-pro
- `/app/backend/routers/voice_agent_router.py` — Retell AI integration
- `/app/backend/services/service_catalog_seeder.py` — seeds 17 services
- `/app/backend/services/trial_scheduler.py` — daily drip + auto-downgrade loop
- `/app/backend/routers/stripe_payment_router.py` — LIVE webhook handling both combo plans + add-ons

### DB Collections
- `service_catalog` (17 services)
- `bundle_rules` (4 auto-discount tiers)
- `primitives` (3 free primitives)
- `customer_subscriptions`
- `trial_sessions`
- `friend_scans`, `friend_scan_views`
- `pixel_dev_emails`
- `catalog_events`, `catalog_audit_log`
- `drip_campaigns_log`

---

## 🎙 VOICE AGENT SYSTEM (Phase 6 — consolidated iter 255)

### Consolidated ✅
- `/app/backend/routers/voice_agent_router.py` — NEW, unified admin + customer endpoints + Retell webhook

### Still fragmented (candidates for future consolidation)
- `voice_router.py` — legacy
- `voice_analytics_router.py` — analytics only (keep separate)
- `voice_profile_router.py` — profile management
- `voice_sales_agent.py` — sales-specific
- `voicebox_router.py` — ORA Chat TTS (different concern, keep)
- `vapi_voice_router.py` — Vapi fallback

### Frontend
- `/app/frontend/src/platform/VoiceSalesAgent.jsx` — legacy sales agent page
- `/app/frontend/src/platform/VoiceAnalytics.jsx` — legacy analytics
- `/app/frontend/src/platform/admin/VoiceAgentStudio.jsx` — NEW unified admin UI (Command Hub tab)

### Providers
- **Retell AI** (primary) — needs `RETELL_API_KEY`
- **ElevenLabs** (TTS) — key set ✅
- **Deepgram** (STT) — key set ✅
- **Twilio** (SIP routing) — set ✅

---

## 📇 CRM SYSTEM

### Backend routers
- `crm_router.py`, `crm_sync_engine.py`
- `lead_enrichment_router.py`, `lead_lifecycle_router.py`, `leads_router.py`
- `pipeline_router.py`, `sales_pipeline.py`
- `omnichannel_hub.py`

### Frontend pages
- `CRMConnect.jsx`, `LeadsDashboard.jsx`, `LeadEnrichmentDashboard.jsx`
- `PipelineDashboard.jsx`, `SalesPipelineDashboard.jsx`, `CampaignDashboard.jsx`

### Consolidation target
Command Hub tabs: Pipeline + Campaigns (currently stub, point to legacy screens)

---

## 🚨 RULES FOR NEW FEATURES

Before building NEW onboarding/tour/wizard:
1. Check this file first
2. Extend existing components when possible
3. Only create new file if truly missing

Before building NEW CRM/voice endpoints:
1. Check if existing router already handles it
2. Consolidate into Command Hub tabs, not new sidebar items
3. Prefer adding tabs/sections to existing unified screens

---

## 🗂 FILE LOCATIONS QUICK REFERENCE

```
/app/backend/
├── routers/         (230+ routers)
├── services/        (business logic)
├── models/          (Pydantic models)
└── server.py        (FastAPI entrypoint, non-blocking startup)

/app/frontend/src/
├── platform/        (admin + customer pages)
│   ├── admin/       (admin-specific sub-pages)
│   ├── customer/    (customer /my/* pages)
│   └── AuremDashboard.jsx  (main admin shell + sidebar)
├── components/      (shared components — includes QuickStartWizard)
└── App.js           (routing entry)

/app/memory/
├── PRD.md           (product requirements, current state)
├── SYSTEM_MAP.md    (this file — system topology)
└── test_credentials.md  (demo login creds)
```
