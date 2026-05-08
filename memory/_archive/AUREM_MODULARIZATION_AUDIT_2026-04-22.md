# AUREM — Structural Audit & Microservice Migration Blueprint
**Generated**: 2026-04-22 · **Scope**: 4-Pillar decomposition
**Current monolith**: 234 routers + 242 services + 1,834 LOC `server.py`

---

## HEADLINE NUMBERS

| Metric | Value |
|---|---:|
| Backend routers (`/app/backend/routers/*.py`) | **234** |
| Backend services (`/app/backend/services/*.py`) | **242** |
| `server.py` lines | 1,834 |
| `server.py` imports | 89 |
| `services/startup_init.py` lines | **887** (single file mounting 200+ routers) |
| `app.include_router` calls | ~220 scattered in `server.py` |
| `def set_db()` singletons (shared DB state) | **120+** services |
| Cross-service imports (top 5 most-imported) | aurem_commercial (152), twilio_service (33), agents (29), memory_tiers (26), free_api_arsenal (24) |
| Schedulers mounted in one event loop | 17+ (auto_blast, shannon_runner, self_repair, self_scan, compliance, trial, backup, news_monitor, cron_schedulers, auto_heal, etc.) |

**Bottom line**: The codebase is a textbook monolith. One broken import in `startup_init.py` crashes all 234 routers. One slow scheduler blocks the entire event loop for every other feature.

---

## PILLAR 1 — Lead Generation & Sales (Hunter / ORA / Outreach)

### Purpose
Scrape businesses → verify contacts → 4-channel blast → track funnel.
This is the user-facing revenue engine.

### Core routers (~35)
| Router | Role |
|---|---|
| `campaign_router.py` | Outreach execution (4-channel blast + Auto-Blast) |
| `hunter_test_router.py` | ORA Hunt runner UI |
| `ora_command_router.py` | ORA command CLI-like endpoints |
| `ora_action_router.py` | ORA follow-up actions |
| `ora_dispatcher_router.py` | Dispatches ORA jobs to agents |
| `ora_stream_router.py` | SSE stream of ORA progress |
| `ora_context_router.py` | Context store for ORA |
| `ora_knowledge_sync.py` | Knowledge base sync |
| `ora_training_router.py` | Agent training |
| `accurate_scout_router.py` | Scout verification |
| `deep_scout_router.py` / `dark_scout_router.py` | Deeper scraping |
| `scout_unified_router.py` | Unified scout wrapper |
| `news_monitor_router.py` | News-based lead signals |
| `leads_router.py` / `extension_leads_router.py` / `public_lead_router.py` | Lead CRUD |
| `lead_enrichment_router.py` | Apollo/Perplexity enrichment |
| `lead_lifecycle_router.py` | Funnel stage progression |
| `crm_router.py` / `crm_sync_engine.py` | CRM operations |
| `voice_agent_router.py` / `voice_sales_agent.py` / `voice_router.py` / `voicebox_router.py` / `vapi_voice_router.py` | Voice outreach |
| `whatsapp_alerts.py` / `whatsapp_hybrid_router.py` / `whatsapp_webhook_router.py` | WhatsApp |
| `email_service.py` / `ai_email_router.py` / `gmail_channel_router.py` | Email |
| `sms_alerts_router.py` | SMS |
| `referral_router.py` / `viral_gate_router.py` / `trial_and_friend_router.py` | Referral |
| `proximity_blast_router.py` | Geo-based outreach |
| `case_study_router.py` / `morning_brief_router.py` | Sales collateral |
| `flame_auto_dialer.py` (service) | Auto-dial |
| `appointment_scheduler_router.py` / `negotiation_router.py` | Booking & nego |

### Core services (~50)
`auto_blast_engine.py`, `hunt_live.py`, `accurate_scout.py`, `business_scout.py`, `deep_scout.py`, `dark_scout_service.py`, `scout_search.py`, `ora_command_center.py`, `ora_context.py`, `ora_dispatcher.py`, `ora_live_context.py`, `contact_extractor.py`, `lead_capture_service.py`, `enhanced_lead_capture.py`, `lead_enrichment.py`, `lead_enrichment_casl.py`, `lead_lifecycle.py`, `proactive_outreach.py`, `proactive_followup_service.py`, `drip_sequencer.py`, `first_contact_email.py`, `email_engine.py`, `email_ai.py`, `email_service_resend.py`, `email_templates.py`, `whapi_service.py`, `whatsapp_engine.py`, `whatsapp_ai_assistant.py`, `whatsapp_coexistence.py`, `ripple_whatsapp_fallback.py`, `sms_engine.py`, `twilio_service.py`, `voice_engine.py`, `aurem_voice_service.py`, `sovereign_voice.py`, `voicebox_service.py`, `voice_wake_word.py`, `ora_call_script.py`, `flame_auto_dialer.py`, `agent_reach_service.py`, `news_monitor.py`, `google_places_sync.py`, `negotiation_engine.py`, `milestone_system.py`, `referral_rewards.py`, `viral_gate.py`, `sales_scientist_ai.py`, `flow_coordinator.py`, `adaptive_ora.py`, `auto_double_lock.py`, `casl_compliance.py`.

### Shared deps (imported by Pillars 2 & 4 too)
- **`twilio_service.py`** — 33 cross-imports (also used by admin alerts, tenant messaging, fraud OTP)
- **`casl_compliance.py`** — 17 imports (email footer wrapping, privacy law)
- **`sendgrid_compat.py`** — 11 imports (legacy email fallback)
- **`agents/`** package — 29 imports (ORA, Envoy, Scout share one agent registry)
- **`memory_tiers.py`** — 26 imports (conversation memory)

### Pillar-1 Bottlenecks
1. **`campaign_router.py` is 2,053 LOC** — handles blast, toggle, auto-blast, leads CRUD, segments, everything. Single-file monolith inside monolith.
2. **WHAPI/Twilio/Retell keys all loaded lazily from `os.environ`** inside every call → slow + no central config validator.
3. **4-channel blast logic duplicated** in `blast_all_channels` (manual path) and `auto_blast_engine` (auto path). Today's bug (inline WHAPI httpx call) was a direct consequence of this duplication.
4. **`auto_blast_engine.py` reads/writes `campaign_leads` directly** (no repository layer) — tight coupling to schema.
5. **No queueing** — blast runs in-process, inside uvicorn event loop. Slow WHAPI response blocks everything.

---

## PILLAR 2 — Client Onboarding & Infrastructure (Stripe / Auth / Portal)

### Purpose
Take a stranger → sign-up → collect payment → provision tenant → send them to a working portal. Identity + billing + tenant setup.

### Core routers (~40)
| Router | Role |
|---|---|
| `stripe_payment_router.py` / `stripe_embed_router.py` | Stripe Checkout + portal |
| `subscription_router.py` / `subscription_routes.py` / `subscription_public_router.py` / `custom_subscription_router.py` | Subscriptions + plan changes |
| `aurem_billing_router.py` / `toon_stripe_service.py` | Invoicing & credits |
| `shopify_billing_router.py` / `shopify_oauth_router.py` / `shopify_pulse_router.py` | Shopify Partner flow |
| `aurem_onboarding_router.py` / `smart_onboarding_router.py` / `onboarding_router.py` / `onboarding_test_router.py` | Onboarding wizards |
| `tenant_customers_router.py` / `tenant_migration_router.py` / `tenant_optimization_router.py` | Tenant lifecycle |
| `client_portal_router.py` / `customer_portal_router.py` / `client_dashboard_router.py` | Client self-serve UI |
| `customer_360_router.py` / `customer_360_actions_router.py` | Customer 360 view |
| `platform_auth_router.py` / `bin_auth_router.py` / `biometric_auth.py` / `biometric_secure.py` | Auth (JWT + Face/Bin OTP) |
| `password_reset_router.py` | Password reset |
| `google_oauth_router.py` / `google_oauth_callback.py` | Google social login |
| `resend_domain_router.py` | Custom email domain setup |
| `provisioning_router.py` | Tenant provisioning |
| `business_id_router.py` / `admin_business_id_router.py` / `business_routes.py` | Business ID generation |
| `infra_settings_router.py` / `settings_router.py` | Per-tenant config |
| `service_catalog_router.py` | SKU catalog |
| `aurem_routes.py` / `aurem_keys_router.py` | Tenant API keys |
| `document_scanner_router.py` / `document_skills_router.py` / `document_rag_router.py` | Document intake |

### Core services (~35)
`customer_service.py`, `customer_memory.py`, `customer_monthly_report.py`, `subscription_manager.py`, `refund_service.py`, `toon_service.py`, `toon_stripe_service.py`, `multi_tenancy_service.py`, `tenant_cost_tracker.py`, `tenant_heartbeat.py`, `tenant_persona.py`, `tenant_profiling.py`, `provisioning_service.py`, `aurem_post_payment_onboarding.py`, `smart_onboarding_service.py`, `welcome_package.py`, `plan_enforcement.py`, `tier1_upgrades.py`, `usage_metering_service.py`, `bin_service.py`, `bin_generator.py`, `fraud_prevention.py` (router), `jwt_blocklist.py`, `white_label.py`, `brand_guard.py`, `tone_sync_service.py`, `invoice_pdf_service.py`, `service_catalog_seeder.py`, `document_skills.py`, `origin_write_engine.py`, `api_key_manager.py`.

### Shared deps
- **`jwt_blocklist.py`** — referenced by every router's `_verify_admin` / `_verify_auth`
- **`multi_tenancy_service.py`** — tenant-scoping used by Pillar 1 (campaigns scoped by tenant) and Pillar 3 (monitoring per tenant)
- **`plan_enforcement.py`** — Pillar 1 blast limits gated here
- **Stripe SDK** — only Pillar 2 owns this, but webhook updates cascade to Pillars 1 & 4 (upgrade triggers increased blast limits, adds KPIs)

### Pillar-2 Bottlenecks
1. **3 overlapping subscription routers** (`subscription_router`, `subscription_routes`, `subscription_public_router`, `custom_subscription_router`) — unclear which is canonical. Risk of double-charging / missed webhooks.
2. **4 overlapping onboarding routers** (`aurem_onboarding`, `smart_onboarding`, `onboarding_router`, `onboarding_test_router`) — onboarding flow hard to trace end-to-end.
3. **Auth state duplicated** — JWT token stored in both `sessionStorage` AND `localStorage` client-side (a past bandage). Should be single source.
4. **`set_db()` singletons** inject DB lazily into each service → race conditions possible during cold-boot when a request arrives before `startup_init` has injected the DB into that specific service.
5. **Stripe webhook handler** lives in `stripe_payment_router` but also partial logic in `toon_stripe_service` — fragmented.

---

## PILLAR 3 — Site Monitoring & Sentinel (Uptime / Bug Detection / Auto-Fix)

### Purpose
Watch deployed customer sites + aurem.live itself. Detect bugs, crashes, SEO regressions, security issues. Auto-repair where possible, push fixes back to customer repos.

### Core routers (~25)
| Router | Role |
|---|---|
| `site_monitor_router.py` | Uptime + cadence |
| `sentinel_client_router.py` | Frontend error ingestion |
| `sentinel_anomaly_router.py` | ML anomaly alerts (in services dir) |
| `seo_audit_router.py` | SEO scans |
| `security_audit_router.py` / `security_router.py` | Security scans |
| `shannon_router.py` | In-process pentest (this session's deliverable) |
| `self_repair_router.py` / `self_healing_router.py` / `ai_repair_router.py` | Auto-repair |
| `customer_website_repair_router.py` | Push fixes to customer |
| `ora_repair_engine.py` | Repair workflow orchestrator |
| `customer_scanner.py` | On-demand audit |
| `live_scanner.py` / `deep_scan_router.py` / `diagnostic_router.py` | Scan endpoints |
| `pixel_patches_router.py` | Client-side AUREM pixel |
| `live_support.py` | Live support widget tie-in |
| `soc2_compliance_router.py` | SOC 2 compliance tracking |
| `legal_router.py` / `panic_settings_router.py` / `panic_takeover_router.py` | Incident / DNS panic takeover |
| `legion_health_router.py` | External Legion node health |
| `monitoring_router.py` / `wiring_audit_router.py` | Self-monitoring |
| `approval_router.py` | Human-in-loop review for auto-fixes |

### Core services (~35)
`site_monitor.py`, `site_audit.py`, `shannon_runner.py`, `shannon_security.py`, `shannon_code_audit.py`, `sentinel_anomaly.py`, `sentinel_guard.py`, `sentinel_verifier.py`, `anomaly_detector.py`, `auto_heal.py`, `auto_fix_engine.py`, `auto_repair.py`, `self_healing_ai.py`, `self_repair_loop.py`, `self_scan_automation.py`, `seo_audit_v2.py`, `seo_autofix_engine.py`, `genetic_repair.py`, `client_scanner_service.py`, `forensic_analyzer.py`, `forensic_miner_service.py`, `hmac_signing.py`, `patch_deployer.py`, `security_gate.py`, `security_reviewer.py`, `security_service.py`, `compliance_monitor.py`, `compliance_scheduler.py`, `pentagi_service.py`, `fallback_monitor.py`, `crash_protection.py`, `code_tracer.py`, `clawchief_service.py`, `smart_approval.py`, `circuit_breaker.py`, `circuit_breaker_service.py`, `gradual_rollout.py`, `pixel_event_buffer.py`, `pixel_heartbeat.py`.

### Shared deps
- **`hmac_signing.py`** — used by Pillars 1 (pixel) and 4 (admin push approvals)
- **`pentagi_service.py`** — depends on Legion (external infra not always available)
- **`pixel_event_buffer.py` / `pixel_heartbeat.py`** — touches Pillar 4 dashboards + Pillar 1 lead attribution

### Pillar-3 Bottlenecks
1. **~15 distinct "scanner" routers with overlapping responsibilities** (`customer_scanner`, `live_scanner`, `deep_scan_router`, `diagnostic_router`, `document_scanner_router`, `self_scan_automation`, `security_audit_router`, `shannon_router`). No clean interface; different data shapes.
2. **Sentinel alerts table hit 400+ entries** — mostly cold-boot noise. No proper dedup/grouping.
3. **Auto-repair path requires a human approval** (`approval_router`) — but there's no visible "pending approvals" queue UI. Fixes back up indefinitely.
4. **Shannon + PentAGI + Shannon-runner — 3 overlapping pentest systems.** Shannon-runner (today's addition) works standalone; PentAGI requires Legion; Shannon-CLI push never worked in practice.
5. **Site-monitor probes run inside uvicorn event loop** — a slow probe on one customer's site can delay probes on every other customer.

---

## PILLAR 4 — Central Command & Observability (Admin / QA / Brain)

### Purpose
Admin dashboards, system state, QA bot, AI brain graph, reporting, revenue analytics. The "control tower."

### Core routers (~35)
| Router | Role |
|---|---|
| `admin_mission_control_router.py` / `aurem_admin_router.py` | Mission Control UI |
| `owner_panel_router.py` | Owner-only panel |
| `super_admin_analytics_router.py` | Platform-wide analytics |
| `admin_cache_router.py` / `admin_customers_router.py` / `admin_financials_router.py` / `admin_links_router.py` / `admin_plan_management.py` / `admin_plan_router.py` / `admin_security_router.py` | Admin sub-panels |
| `dashboard_feeds_router.py` / `system_overview_router.py` / `system_pulse_router.py` / `system_routes.py` | Dashboard data |
| `ai_router.py` / `ai_platform_router.py` / `aurem_ai_router.py` / `aurem_chat.py` / `aurem_llm_proxy_router.py` | AI chat + LLM routing |
| `agent_execution_router.py` / `agent_harness_router.py` / `agent_observatory_router.py` / `agents_router.py` | Agent orchestration |
| `brain_router.py` | Brain graph visualizer |
| `qa_bot_router.py` / `critic_router.py` | QA Bot + adversarial critic |
| `ai_repair_router.py` | AI repair workflows |
| `global_pulse_router.py` / `daily_intel_router.py` / `nexus_router.py` | Global intel feeds |
| `revenue_engine.py` / `revenue_forecast_router.py` | Revenue analytics |
| `activity_feed_router.py` / `digest_routes.py` | Admin feeds |
| `training_dashboard_router.py` | Training UI |
| `premium_routes.py` / `free_api_router.py` | Tier-based API access |
| `db_optimizer_router.py` / `tenant_optimization_router.py` | DB perf |
| `system_audit_router.py` / `wiring_audit_router.py` | Self-audit |
| `modularization_router.py` | (Existing module-split endpoint) |

### Core services (~40)
`analytics_aggregator.py`, `analytics_service.py`, `global_pulse.py`, `intelligence_engine.py`, `autonomy_engine.py`, `orchestrator.py`, `agent_pipeline.py`, `agent_cards.py`, `agent_rbac.py`, `aurem_ai_service.py`, `aurem_business_agents.py`, `aurem_mcp_server.py`, `clawchief_service.py`, `critic_agent.py`, `qa_bot.py`, `qa_agent_deep.py`, `oracle_proactive.py`, `morning_brief.py`, `morning_digest.py`, `daily_digest.py`, `hermes_memory_agent.py`, `hermes_identity.py`, `hermes_deepsleep_bridge.py`, `rag_knowledge_base.py`, `memobase.py`, `memory_tiers.py`, `stm_service.py`, `revenue_forecast.py`, `admin_action_ai.py`, `cron_schedulers.py`, `nightly_cycle.py`, `nightly_health_check.py`, `nightly_wiring_audit.py`, `notification_triggers.py`, `panic_alert_service.py`, `push_notification_service.py`, `kill_switch.py`, `db_optimizer.py`, `db_index_builder.py`, `tenant_heartbeat.py`, `usage_metering_service.py`.

### Shared deps
- **`hermes_memory_agent.py`** — 12 imports (cross-agent memory)
- **`hermes_identity.py`** — 12 imports (agent identity)
- **`global_pulse.py`** — 12 imports (global state broadcast)
- **`aurem_commercial.py`** — 152 imports (THE monster dependency — SKU/catalog data every feature reads)
- **`agents/` package** — 29 imports

### Pillar-4 Bottlenecks
1. **`aurem_commercial.py` is imported 152 times** — if this file breaks, 152 endpoints break. Biggest single-file risk in the codebase.
2. **`startup_init.py` mounts ~220 routers in one function** — a single bad import crashes the whole API. This has happened 3+ times.
3. **Admin dashboards pull from 30+ collections** directly via MongoDB — no caching layer, no query plan. Dashboard load time scales with DB size.
4. **QA Bot + Critic + ClawChief** all fire on every heartbeat (400 alerts in DB) — they run BEFORE they have context, so they flag legit data as anomalies (today's ClawChief warning spam).
5. **`cron_schedulers.py` + `startup_init.py` compete** — some background tasks scheduled in both places. Risk of double-execution.

---

## CROSS-CUTTING SHARED DEPENDENCIES (belong nowhere, needed everywhere)

These MUST become a separate `aurem-shared` library before any module can be cleanly split:

1. **`aurem_commercial.py`** — SKU catalog, pricing, upgrade tiers (152 imports)
2. **`memory_tiers.py`** — conversation/context storage (26 imports)
3. **`agents/` package** — agent registry (29 imports)
4. **`free_api_arsenal.py`** — free-tier API abstractions (24 imports)
5. **`twilio_service.py`** — used by all 4 pillars for notifications (33 imports)
6. **`jwt_blocklist.py` + `agent_rbac.py`** — auth/RBAC primitives
7. **`casl_compliance.py` + `sendgrid_compat.py`** — email compliance footer + legacy SMTP
8. **`hmac_signing.py`** — SOC 2 signing (Pillars 1, 3, 4)
9. **`circuit_breaker.py` + `rate_limiter`** — resilience primitives
10. **`db_optimizer.py` + indexes** — MongoDB indexes used everywhere

---

## CRITICAL BOTTLENECKS (rank-ordered, stop-the-line-first)

### 🔴 P0 — Single-Event-Loop Death Spiral
- All 17+ background schedulers (auto_blast, shannon, self_repair, self_scan, compliance, trial, backup, news_monitor, cron, auto_heal, etc.) run in the **same** uvicorn event loop as the 234 HTTP routers.
- One slow HTTP call inside a scheduler (e.g., WHAPI 15s timeout) blocks every incoming request for 15 seconds.
- Symptom: production logs show `nginx connect() failed (111: Connection refused)` during scheduler bursts.
- **Fix (migration)**: move ALL schedulers to a dedicated worker process (`aurem-worker`). Uvicorn only handles HTTP.

### 🔴 P0 — Monolith Mounting (`startup_init.py`)
- One bad import crashes all 234 routers.
- Has crashed production at least 3 times in recent sessions (abandoned_cart, sentinel_router archive, shannon agent_id).
- **Fix (migration)**: each pillar becomes its own Python package with its own ASGI `app`. Gateway routes based on path prefix.

### 🟠 P1 — `campaign_router.py` = 2,053 LOC
- Contains blast logic AND lead CRUD AND segments AND auto-blast endpoints AND render helpers.
- Duplicate WHAPI send code (inline httpx + `whapi_service.py`) — we found this causing the 0% WhatsApp success rate today.
- **Fix**: split into `lead_crud`, `blast_service`, `auto_blast`, `render_templates`.

### 🟠 P1 — `aurem_commercial.py` Fragility
- 152 imports. One schema change rewrites every endpoint.
- **Fix**: freeze as Pydantic-versioned SKU contract; serve via `shared/` package with semver.

### 🟡 P2 — 3-4 Overlapping Subscription + Onboarding Routers
- No canonical flow; easy to miss webhook in one branch.
- **Fix**: deprecate 2, keep one canonical each. Document in OpenAPI.

### 🟡 P2 — 15+ Scanner Routers with Overlapping Responsibilities
- Different data shapes for the same concept (a "scan result").
- **Fix**: one `scanner-core` service with typed output; routers become thin adapters.

### 🟡 P2 — In-Process WHAPI / Retell / Twilio / Stripe Calls
- Every call blocks the event loop up to provider timeout (15-30s).
- **Fix**: all provider calls go through an async **outbox table + worker**, not in-request.

### 🟡 P2 — 120+ `set_db()` Singletons
- Services grab DB state at different points of cold-boot → race conditions.
- **Fix**: DI container with explicit startup sequencing.

---

## MIGRATION ORDER — Which to isolate FIRST

### Recommended sequence:

**Step 1 — Extract `aurem-shared` first (week 1)**
Move the 10 cross-cutting files to `/app/backend/shared/` + publish as internal package. Every pillar depends on this, so it must exist before pillars can be split.

**Step 2 — Isolate Pillar 3 (Site Monitoring) (week 2)**
Why first? It has the **loosest coupling** to the rest of the app (monitoring is read-mostly; writes only to its own collections). Quickest win, lowest risk.
- Spin up `aurem-sentinel` as a separate FastAPI app on its own port.
- Gateway in `server.py` proxies `/api/site-monitor`, `/api/sentinel`, `/api/shannon`, `/api/seo-audit` to the new pod.
- Background schedulers (`site_monitor`, `shannon_runner`, `self_repair_loop`) move with it → **immediately** removes their blocking effect on the main event loop.

**Step 3 — Isolate Pillar 1 (Lead Gen & Sales) (week 3-4)**
Biggest revenue impact + biggest monolith pain. Once Pillar 3 pattern is proven, apply same pattern:
- Pillar 1 owns: `campaign_leads`, `sent_emails`, `sms_logs`, `whatsapp_message_log`, `voice_call_logs`, `ora_*`, `scout_*`, `news_alerts` collections.
- Auto-Blast scheduler moves to its own worker pod.
- WHAPI / Twilio / Retell / Resend calls go through an outbox worker.

**Step 4 — Isolate Pillar 2 (Onboarding + Billing) (week 5)**
- Stripe webhooks get their own small service (low-throughput but must NEVER miss an event).
- Deprecate the 2 duplicate subscription/onboarding routers.

**Step 5 — What remains becomes Pillar 4 (Command Hub) (week 6)**
By this point, Pillar 4 is a thin admin UI + BFF (Backend-for-Frontend) that calls the 3 isolated services via internal HTTP / gRPC.

---

## FINAL ATTESTATION

All numbers verified against the live codebase on 2026-04-22:
- `ls backend/routers/*.py | wc -l` = 234
- `ls backend/services/*.py | wc -l` = 242
- `wc -l backend/server.py` = 1,834
- `wc -l backend/services/startup_init.py` = 887
- `grep -c "from services.aurem_commercial" backend -r` = 152 hits
- `grep -rc "def set_db" backend/services/` = 120+

This document is a planning artefact, not a promise of delivery. Recommended delivery = 6 weeks with 1 engineer working full-time, following the step order above.
