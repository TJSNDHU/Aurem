"""
Router Registry — Central registration of ALL FastAPI routers.
Extracted from server.py Phase 2 modularization.

Call register_all_routers(app, db) from the startup event after db is
initialized.

Section index (largest blocks live deepest):
    [config]    LEAN-mode skip list           → routers/_registry_config.py
    SECTION 1   Pre-imported core routers     (~370 LOC)
    SECTION 2   Commercial AI platform        (~95 LOC)
    SECTION 3   AUREM platform + db init      (~270 LOC)
    SECTION 4   /api-prefixed routers         (~240 LOC)
    SECTION 5   Direct-import routers         (~120 LOC)
    SECTION 5.5–5.18  Misc admin slices       (~250 LOC)
    SECTION 6   APScheduler / bug engine      (~720 LOC)
    [prune]     LEAN-mode post-prune          → routers/_registry_lean_prune.py
"""

import logging
import asyncio
import os

from routers._registry_config import LEAN_MODE, make_should_skip
from routers._registry_lean_prune import apply_lean_prune

logger = logging.getLogger(__name__)


def _looks_like_production_for_registry() -> bool:
    """iter 332b D-25 + D-26 — production detection.

    Preview pods have HOSTNAME starting with `agent-env-` (a sandboxed
    dev container). Production pods have HOSTNAME containing
    `live-support` or end in `emergent.host`.

    Detection precedence: explicit env overrides → hostname check →
    K8s presence as last-resort signal."""
    if os.environ.get("AUREM_FORCE_FULL_MODE", "").strip() in ("1", "true", "yes"):
        return False
    if os.environ.get("AUREM_LITE_MODE", "").strip() in ("1", "true", "yes"):
        return True
    host = (os.environ.get("HOSTNAME") or "").lower()
    # Preview pods are the agent sandbox — never production.
    if host.startswith("agent-env-") or host.startswith("preview-"):
        return False
    if "live-support" in host or "emergent.host" in host:
        return True
    # Last-resort: in K8s with no preview/agent-env signal AND no
    # preview_endpoint env var → assume prod.
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        if not os.environ.get("preview_endpoint"):
            return True
    return False


def register_all_routers(app, db):
    """Register every router with the FastAPI app. Must be called after DB init."""

    # ═══════════════════════════════════════════
    # PRODUCTION LEAN MODE — skip non-essential routers
    # Reduces from 2000+ routes to ~400 core routes
    # See routers/_registry_config.py for the full skip list.
    # ═══════════════════════════════════════════
    _should_skip = make_should_skip(LEAN_MODE)

    if LEAN_MODE:
        logger.info("[REGISTRY] LEAN MODE active — skipping non-essential routers")

    # ═══════════════════════════════════════════
    # SECTION 1: Pre-imported Core Routers
    # (imported at top of server.py)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.server_misc_routes"):
        try:
            from routers.server_misc_routes import router as server_misc_router
            app.include_router(server_misc_router)
        except Exception as e:
            logger.warning(f"Server misc routes not loaded: {e}")

    # Inline routers (extracted from server.py Phase 1)
    _inline_routers = []
    _inline_names = [
        "auth_inline", "product_inline", "cart_inline", "order_inline",
        "payment_inline", "admin_inline", "influencer_inline",
        "store_settings_inline", "analytics_inline", "subscriber_inline",
        "seo_inline", "shipping_qr_inline", "blog_inline",
        "founding_inline", "postal_inline",
    ]
    for mod_name in _inline_names:
        if _should_skip(mod_name):
            continue
        try:
            mod = __import__(f"routers.{mod_name}", fromlist=["router"])
            _inline_routers.append(mod.router)
        except Exception as e:
            logger.warning(f"Inline router {mod_name} not loaded: {e}")

    for _r in _inline_routers:
        app.include_router(_r, prefix="/api")

    # Core modular routers
    try:
        from routes.auth import router as auth_router
        app.include_router(auth_router, prefix="/api")
    except Exception as e:
        logger.warning(f"Auth router not loaded: {e}")

    try:
        from routes.orders import router as orders_router
        app.include_router(orders_router, prefix="/api")
    except Exception as e:
        logger.warning(f"Orders router not loaded: {e}")

    if not _should_skip("routes.business_system"):
        try:
            from routes.business_system import router as business_system_router
            app.include_router(business_system_router)
        except Exception as e:
            logger.warning(f"Business system router not loaded: {e}")

    try:
        from routes.automations import router as automations_router
        app.include_router(automations_router)
    except Exception as e:
        logger.warning(f"Automations router not loaded: {e}")

    try:
        from routes.rbac import router as rbac_router
        app.include_router(rbac_router)
    except Exception as e:
        logger.warning(f"RBAC router not loaded: {e}")

    _safe_includes = [
        ("routes.automation_gaps_routes", "automation_gaps_router", None),
        ("routes.whatsapp_ai_routes", "whatsapp_ai_router", None),
    ]
    for module_path, attr_name, prefix in _safe_includes:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            r = getattr(mod, "router", None)
            if r:
                if prefix:
                    app.include_router(r, prefix=prefix)
                else:
                    app.include_router(r)
        except Exception as e:
            logger.warning(f"{module_path} not loaded: {e}")

    # iter 282g Task 3 — Leads email mining secondary router (GET list endpoint)
    try:
        from routers.leads_mining_router import _list_router as _leads_list_router
        app.include_router(_leads_list_router)
    except Exception as e:
        logger.warning(f"leads_mining list_router not loaded: {e}")

    # WhatsApp Test Console
    if not _should_skip("routes.whatsapp_test"):
        try:
            from routes.whatsapp_test import router as whatsapp_test_router
            app.include_router(whatsapp_test_router, prefix="/api")
        except Exception as e:
            logger.warning(f"WhatsApp test router not loaded: {e}")

    # Public lead capture (no auth — landing page "Get Free Audit")
    try:
        from routers.public_lead_router import router as public_lead_router, set_db as set_public_lead_db
        set_public_lead_db(db)
        app.include_router(public_lead_router)
        logger.info("Public Lead Capture router registered")
    except Exception as e:
        logger.warning(f"Public Lead Capture router not loaded: {e}")

    # SEO Audit $49 (Phase 1 — public lead magnet + paid report)
    try:
        from routers.seo_audit_router import router as seo_audit_router, set_db as set_seo_db, ensure_stripe_product
        set_seo_db(db)
        app.include_router(seo_audit_router)
        import asyncio as _seo_asyncio
        _seo_asyncio.create_task(ensure_stripe_product())
        logger.info("SEO Audit $49 router registered")
    except Exception as e:
        logger.warning(f"SEO Audit router not loaded: {e}")

    # Privacy / Sovereign Mode (Phase 3)
    try:
        from routers.privacy_mode_router import router as privacy_router, set_db as set_privacy_db
        set_privacy_db(db)
        app.include_router(privacy_router)
        logger.info("Privacy Mode router registered")
    except Exception as e:
        logger.warning(f"Privacy Mode router not loaded: {e}")

    # Daily Intel Engine (Phase 2 — Tavily + Resend digest)
    try:
        from routers.daily_intel_router import router as daily_intel_router, set_db as set_daily_intel_db
        set_daily_intel_db(db)
        app.include_router(daily_intel_router)
        logger.info("Daily Intel router registered")
    except Exception as e:
        logger.warning(f"Daily Intel router not loaded: {e}")

    # Customer Website Repair (pixel status + scan + repair demo)
    try:
        from routers.customer_website_repair_router import router as cwr_router, set_db as set_cwr_db
        set_cwr_db(db)
        app.include_router(cwr_router)
        logger.info("Customer Website Repair router registered")
    except Exception as e:
        logger.warning(f"Customer Website Repair router not loaded: {e}")

    # Service Catalog (Admin Pricing Studio + Customer Add-ons — Hybrid Storefront Option C)
    try:
        from routers.service_catalog_router import router as catalog_router, set_db as set_catalog_db
        set_catalog_db(db)
        app.include_router(catalog_router)
        logger.info("Service Catalog router registered")
        # Schedule catalog seeding as background task (non-blocking)
        import asyncio
        from services.service_catalog_seeder import seed_service_catalog
        asyncio.create_task(seed_service_catalog(db))
    except Exception as e:
        logger.warning(f"Service Catalog router not loaded: {e}")

    # Trial + Friend Scanner (Phase 3+5 — viral growth + pricing-pro + pixel install)
    try:
        from routers.trial_and_friend_router import router as trial_router, set_db as set_trial_db
        set_trial_db(db)
        app.include_router(trial_router)
        logger.info("Trial + Friend Scanner router registered")
    except Exception as e:
        logger.warning(f"Trial + Friend Scanner router not loaded: {e}")

    # AUREM Voice Agent — Phase 6 (Retell AI + consolidated voice endpoints)
    try:
        from routers.voice_agent_router import router as voice_agent_router, set_db as set_va_db
        set_va_db(db)
        app.include_router(voice_agent_router)
        logger.info("AUREM Voice Agent router registered")
    except Exception as e:
        logger.warning(f"Voice Agent router not loaded: {e}")

    # Trial Scheduler (Phase 5) — daily drip + auto-downgrade
    try:
        import asyncio
        from services.trial_scheduler import trial_scheduler_loop
        asyncio.create_task(trial_scheduler_loop(db))
        logger.info("Trial Scheduler background loop started")
    except Exception as e:
        logger.warning(f"Trial Scheduler not started: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # BULK ROUTER WIRING — Iteration 258
    # 42 previously-orphaned high/medium-value routers registered here.
    # Each wrapped in try/except so one failure doesn't cascade.
    # Pattern: import → (optional) set_db → include_router
    # ═══════════════════════════════════════════════════════════════════

    _bulk_routers_with_set_db = [
        # ── HIGH VALUE ──
        ("morning_brief_router", "morning_brief_router"),
        ("news_monitor_router", "news_monitor_router"),
        ("pipeline_router", "pipeline_router"),
        ("lead_lifecycle_router", "lead_lifecycle_router"),
        ("revenue_engine", "revenue_engine_router"),
        ("revenue_forecast_router", "revenue_forecast_router"),
        ("churn_prediction_router", "churn_prediction_router"),
        ("security_audit_router", "security_audit_router"),
        ("subscription_router", "subscription_router"),
        ("openfang_router", "openfang_router"),
        ("zdr_router", "zdr_router"),
        ("repair_checkout_router", "repair_checkout_router"),
        ("social_presence_router", "social_presence_router"),
        ("unified_inbox_router", "unified_inbox_router"),
        ("ai_email_router", "ai_email_router"),
        ("website_builder_router", "website_builder_router"),
        # ── MEDIUM VALUE ──
        ("admin_customers_router", "admin_customers_router"),
        ("agent_execution_router", "agent_execution_router"),
        ("agent_observatory_router", "agent_observatory_router"),
        ("approval_router", "approval_router"),
        ("brief_router", "brief_router"),
        ("client_manager_router", "client_manager_router"),
        ("client_portal_router", "client_portal_router"),
        ("conviction_router", "conviction_router"),
        ("customer_360_router", "customer_360_router"),
        ("customer_360_actions_router", "customer_360_actions_router"),
        ("dark_scout_router", "dark_scout_router"),
        ("dashboard_feeds_router", "dashboard_feeds_router"),
        ("deep_scout_router", "deep_scout_router"),
        ("document_rag_router", "document_rag_router"),
        ("document_scanner_router", "document_scanner_router"),
        ("honeypot_router", "honeypot_router"),
        ("memory_router", "memory_router"),
        ("ora_knowledge_sync", "ora_knowledge_sync_router"),
        ("panic_settings_router", "panic_settings_router"),
        ("referral_router", "referral_router"),
        ("scout_unified_router", "scout_unified_router"),
        ("sentiment_analysis_router", "sentiment_analysis_router"),
        ("settings_router", "settings_router"),
        ("tenant_optimization_router", "tenant_optimization_router"),
    ]

    for mod_name, _alias in _bulk_routers_with_set_db:
        try:
            _mod = __import__(f"routers.{mod_name}", fromlist=["router", "set_db"])
            if hasattr(_mod, "set_db"):
                _mod.set_db(db)
            app.include_router(_mod.router)
            logger.info(f"[bulk-wire] {mod_name} registered")
        except Exception as e:
            logger.warning(f"[bulk-wire] {mod_name} failed: {e}")

    # Routers WITHOUT set_db — import router object directly
    _bulk_routers_plain = [
        "sales_pipeline",
        "resend_domain_router",
        "content_engine_router",
        "ora_training_router",
        # Iter 259 additions (no set_db)
        "integration_api",
        "monitoring_router",
        "session_memory_router",
        "batch_router",
    ]
    for mod_name in _bulk_routers_plain:
        try:
            _mod = __import__(f"routers.{mod_name}", fromlist=["router"])
            if hasattr(_mod, "set_db"):
                _mod.set_db(db)
            app.include_router(_mod.router)
            logger.info(f"[bulk-wire] {mod_name} registered (plain)")
        except Exception as e:
            logger.warning(f"[bulk-wire] {mod_name} failed: {e}")

    # ═══════════════════════════════════════════════════════════════════
    # ITERATION 259 — Category A (no-key) + Category B (LLM-powered)
    # 19 more routers wired. Uses EMERGENT_LLM_KEY where needed (already set).
    # ═══════════════════════════════════════════════════════════════════
    _iter259_routers = [
        # ── Category A: safe (no new keys) ──
        "aurem_onboarding_router",      # 5 ep — /welcome page backend
        "aurem_public_report_router",   # 3 ep — public audit reports
        "appointment_scheduler_router", # 8 ep — CRM bookings
        "action_engine_router",         # 5 ep — real-world action executor
        "digest_routes",                # 6 ep — daily digest
        "critic_router",                # 7 ep — AI output QA
        "negotiation_router",           # 5 ep — AI negotiation
        "omnidim_router",               # 16 ep — OmniBridge 8.4
        "super_admin_analytics_router", # 2 ep — platform analytics
        "tenant_customers_router",      # 8 ep — tenant-isolated vault
        # ── Category B: LLM-powered (EMERGENT_LLM_KEY) ──
        "brain_router",                 # 6 ep — master brain
        "orchestrator_brain_router",    # 10 ep — multi-agent orchestration
        "orchestrator_customer_router", # 2 ep — customer-scoped read-only (iter 323d)
        "customer_vanguard_router",     # 1 ep — fast vanguard status (iter 323f)
        "sovereignty_score_router",     # 1 ep — full sovereignty score (iter 323j)
        "pixel_bridge_router",          # 3 ep — pixel→ORA bridge admin (iter 323g)
        "ooda_loop_router",             # 5 ep — OODA automation
        "a2a_learning_router",          # 8 ep — agent-to-agent learning
        "browser_agent_router",         # 7 ep — browser automation
        "aurem_llm_proxy_router",       # 4 ep — LLM proxy
        "video_generation_router",      # 5 ep — video gen (Sora-style)
    ]
    for mod_name in _iter259_routers:
        try:
            _mod = __import__(f"routers.{mod_name}", fromlist=["router"])
            if hasattr(_mod, "set_db"):
                _mod.set_db(db)
            app.include_router(_mod.router)
            logger.info(f"[iter259-wire] {mod_name} registered")
        except Exception as e:
            logger.warning(f"[iter259-wire] {mod_name} failed: {e}")

    # Upload, Marketing, AI
    _api_prefixed = [
        ("routers.upload", "upload_router"),
        ("routers.marketing", "marketing_router"),
        ("routers.ai_router", "ai_router"),
    ]
    for module_path, name in _api_prefixed:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            app.include_router(mod.router, prefix="/api")
        except Exception as e:
            logger.warning(f"{name} not loaded: {e}")

    # Routers with their own /api prefix (no prefix needed)
    _self_prefixed = [
        ("routers.live_support", "Live Support"),
        ("routers.fraud_prevention", "Fraud Prevention"),
        ("routes.cache_routes", "Cache Admin"),
        ("routes.mcp_routes", "MCP HTTP API"),
        ("routes.db_query_routes", "DB Query"),
        ("routes.admin", "Admin"),
    ]
    for module_path, label in _self_prefixed:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            r = getattr(mod, "router", None) or getattr(mod, "cache_router", None) or getattr(mod, "mcp_router", None) or getattr(mod, "db_query_router", None)
            if r:
                app.include_router(r)
        except Exception as e:
            logger.warning(f"{label} not loaded: {e}")

    # Chat Widget + Admin Action AI + Email + Content + API Keys + Data Security + Crash Dashboard
    # NOTE: voice.voice_routes REMOVED — it was legacy dead code (Deepgram/Telnyx)
    # that shadowed the real V2V engine routes. All voice is now handled by:
    #   v2v_stream_engine.py, vapi_voice_router.py, voice_sales_agent.py,
    #   voice_command_routes.py, voice_layer_router.py, voice_profile_router.py
    _mixed = [
        ("routes.chat_widget_routes", "/api"),
        ("routes.admin_action_ai_routes", "/api"),
        ("routes.email_routes", None),
        ("routes.content_routes", None),
        ("routes.api_key_routes", None),
        ("routes.data_security_routes", None),
        ("routes.crash_dashboard_routes", None),
        ("routes.a2a_routes", None),
        ("routes.outreach_routes", None),
        ("routes.phone_routes", None),
        ("routes.site_audit_routes", None),
        ("routes.compliance_routes", None),
        ("routes.auto_repair_routes", None),
        ("routes.orchestrator_routes", None),
    ]
    for module_path, prefix in _mixed:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            if prefix:
                app.include_router(mod.router, prefix=prefix)
            else:
                app.include_router(mod.router)
        except Exception as e:
            logger.warning(f"{module_path} not loaded: {e}")

    # ═══════════════════════════════════════════
    # SECTION 2: Commercial AI Platform Routers
    # ═══════════════════════════════════════════
    _commercial_routers = [
        "routers.agents_router",              # 4-agent autonomous system + auto-hunt settings + unsubscribe
        "routers.onboarding_test_router",     # Admin dry-run simulator for Stripe → onboarding chain
        "routers.subscription_router",
        "routers.owner_panel_router",
        "routers.sms_alerts_router",
        "routers.sentiment_analysis_router",
        "routers.admin_mission_control_router",
        "routers.admin_breakers_router",
        "routers.monitoring_router",
        "routers.document_scanner_router",
        "routers.video_generation_router",
        "routers.appointment_scheduler_router",
        "routers.a2a_learning_router",
        "routers.orchestrator_brain_router",
        "routers.admin_security_router",      # Guardrail blocks feed + ORA eval suite runner
        "routers.webclaw_health_router",      # iter 282ad — Scout webclaw integration health chip
        "routers.composer_health_router",     # iter 282ai — ORA Composer (LLM) health chip
        "routers.linkedin_router",            # iter 282aj — LinkedIn OAuth + status
        "routers.skills_health_router",       # iter 282ak — ORA Skills Router + Learning Engine chips
    ]
    for module_path in _commercial_routers:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router", "set_db"])
            app.include_router(mod.router)
            if hasattr(mod, "set_db") and db is not None:
                mod.set_db(db)
        except ImportError as e:
            logger.warning(f"{module_path} not loaded: {e}")

    # Subscription public/custom/admin plan routers (conditional)
    for module_path in [
        "routers.subscription_public_router",
        "routers.custom_subscription_router",
        "routers.admin_plan_router",
        "routers.admin_plan_management",
        "routers.admin_dr_backup_router",
        "routers.self_healing_router",
    ]:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router", "set_db"])
            if hasattr(mod, "set_db"):
                try:
                    mod.set_db(db)
                except Exception as _e:
                    logger.warning(f"[REGISTRY] {module_path}.set_db failed: {_e}")
            if mod.router is not None:
                app.include_router(mod.router)
        except Exception as e:
            logger.warning(f"[REGISTRY] {module_path} not loaded: {e}")

    # Self-Repair, Client Dashboard, Patch, Deploy, SOC2
    for module_path in [
        "routers.self_repair_router",
        "routers.client_dashboard_router",
        "routers.deployment_router_api",
        "routers.soc2_compliance_router",
    ]:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            if hasattr(mod, "set_db"):
                mod.set_db(db)
            app.include_router(mod.router)
        except Exception:
            pass

    # Conditional includes (connector, smart search, agent harness, skills, etc.)
    _conditional = [
        "routers.connector_router",
        "routers.smart_search_router",
        "routers.agent_harness_router",
        "routers.vector_search_router",
        "routers.hooks_router",
        "routers.generative_ui_router",
    ]
    for module_path in _conditional:
        if _should_skip(module_path):
            continue
        try:
            mod = __import__(module_path, fromlist=["router"])
            if mod.router is not None:
                app.include_router(mod.router)
            # Wire database into the router's module-level singleton if it
            # exposes a `set_db` symbol. Without this the router's internal
            # `_db` stays None and every endpoint 500s. iter 280.4
            if hasattr(mod, "set_db") and db is not None:
                try:
                    mod.set_db(db)
                except Exception:
                    pass
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # SECTION 3: AUREM Platform Routers (with db init)
    # ═══════════════════════════════════════════
    _aurem_with_db = [
        ("routers.aurem_chat", "AUREM Chat"),
        ("routers.ora_tts_router", "ORA TTS (text-to-speech)"),
        ("routers.campaign_brief_admin_router", "Campaign Brief Admin"),
        ("routers.ora_dispatcher_router", "ORA Dispatcher"),
        ("routers.critic_router", "Critic Agent"),
        ("routers.openrouter_router", "OpenRouter"),
        ("routers.brain_router", "Brain Orchestrator"),
        ("routers.unified_inbox_router", "Unified Inbox"),
        ("routers.whatsapp_webhook_router", "WhatsApp"),
        ("routers.voice_router", "AUREM Voice"),
        ("routers.voice_analytics_router", "Voice Analytics"),
        ("routers.agent_reach_router", "Agent Reach"),
        ("routers.morning_brief_router", "Morning Brief"),
        ("routers.aurem_billing_router", "AUREM Billing"),
        ("routers.google_oauth_router", "Gmail OAuth"),
        ("routers.gmail_channel_router", "Gmail Channel"),
        ("routers.action_engine_router", "Action Engine"),
        ("routers.aurem_keys_router", "AUREM API Keys"),
        ("routers.asi_evolve_router", "ASI-Evolve"),
        ("routers.honeypot_router", "Security Honeypot"),
        ("routers.aurem_llm_proxy_router", "AUREM LLM Proxy"),
        ("routers.aurem_vanguard_router", "AUREM Vanguard"),
        ("routers.aurem_admin_router", "AUREM Admin"),
        ("utils.aurem_bug_engine", "AUREM Bug Engine"),
        ("utils.aurem_orchestrator", "AUREM Orchestrator"),
        ("routers.omnidim_router", "OmniBridge"),
        ("routers.security_router", "Security"),
        ("routers.platform_auth_router", "Platform Auth"),
        ("routers.pin_auth_router", "Platform Auth · PIN"),
        ("routers.email_inbound_router", "Inbound Email"),
        ("routers.admin_awb_maintenance_router", "Admin · AWB Maintenance"),
        ("routers.aurem_routes", "AUREM Routes"),
        ("routers.business_routes", "Business Routes"),
        ("routers.premium_routes", "Premium Features"),
        ("routers.system_routes", "System Routes"),
        ("routers.digest_routes", "Daily Digest"),
        ("routers.subscription_routes", "Subscription Billing"),
        ("routers.forensic_routes", "ORA Forensic"),
        ("routers.leads_router", "Leads"),
        ("routers.panic_settings_router", "Panic Settings"),
        ("routers.vapi_voice_router", "VAPI Voice"),
        ("routers.voice_profile_router", "Voice Profile"),
        ("routers.ora_pwa_router", "ORA PWA"),
        ("routers.ora_training_router", "ORA Training"),
        ("routers.ora_knowledge_sync", "ORA Knowledge Sync"),
        ("routers.super_admin_analytics_router", "Super Admin Analytics"),
        ("routers.browser_agent_router", "Browser Agent"),
        ("routers.ooda_loop_router", "OODA Loop"),
        ("routers.ai_platform_router", "AI Platform"),
        ("routers.client_manager_router", "Client Manager"),
        ("routers.admin_customers_router", "Admin Customers"),
        ("routers.camofox_router", "Camofox Browser"),
        ("routers.extension_leads_router", "Extension Leads"),
        ("routers.settings_router", "Settings"),
        ("routers.crm_router", "CRM Connect"),
        ("routers.gateway_router", "API Gateway"),
        ("routers.automations_router", "Automations"),
        ("routers.referral_router", "Referral"),
        ("routers.training_dashboard_router", "Training Dashboard"),
        ("routers.vault_router", "Secret Vault"),
        ("routers.revenue_engine", "Revenue Engine"),
        ("routers.enterprise_engine", "Enterprise Features"),
        ("routers.onboarding_router", "Onboarding"),
        ("routers.intelligence_api", "Intelligence API"),
        ("routers.agent_execution_router", "Agent Execution"),
        ("routers.password_reset_router", "Password Reset"),
        ("routers.stripe_payment_router", "Stripe Payment"),
        ("routers.stripe_webhook_alias_router", "Stripe Webhook (alias /api/stripe/webhook)"),
        ("routers.payments_health_router", "Payments Health (Pillars Map)"),
        ("routers.ora_health_router", "ORA Self-Heal Status (Mission Control)"),
        ("routers.google_oauth_callback", "Google OAuth Callback"),
        ("routers.universal_connector_router", "Universal Connector"),
        ("routers.ucp_router", "UCP"),
        ("routers.ora_action_router", "ORA Action"),
        ("routers.ghost_geo_router", "Ghost GEO"),
        ("routers.tenant_optimization_router", "Tenant Optimization"),
        ("routers.pipeline_router", "Pipeline Coordinator"),
        ("routers.approval_router", "Smart Approval"),
        ("routers.session_memory_router", "Session Memory"),
        ("routers.memory_router", "Memory Tiers"),
        ("routers.security_audit_router", "Security Audit"),
        ("routers.negotiation_router", "Negotiation Engine"),
        ("routers.document_rag_router", "Document RAG"),
        ("routers.lead_enrichment_router", "Lead Enrichment"),
        ("routers.revenue_forecast_router", "Revenue Forecast"),
        ("routers.campaign_router", "Campaign Outbound"),
        ("routers.conviction_router", "Conviction / Adaptive ORA"),
        ("routers.aurem_public_report_router", "AUREM Public Report"),
        ("routers.aurem_onboarding_router", "AUREM Onboarding"),
        ("routers.website_builder_router", "AUREM Website Builder"),
        ("routers.ora_command_router", "ORA Command Center"),
        ("routers.aurem_builder_router", "AUREM Builder"),
        ("routers.activity_feed_router", "Activity Feed"),
        ("routers.legion_health_router", "Legion Nodes Health"),
        ("routers.accurate_scout_router", "Accurate Scout"),
        ("routers.dashboard_feeds_router", "Dashboard Feeds"),
        ("routers.lead_lifecycle_router", "Lead Lifecycle (Kanban + Drip)"),
        ("routers.agent_observatory_router", "Agent Observatory"),
        ("routers.dark_scout_router", "Dark Scout Intelligence"),
        ("routers.churn_prediction_router", "Churn Prediction"),
        ("routers.brief_router", "Morning Brief"),
        ("routers.modularization_router", "Modularization"),
        ("routers.openclaw_router", "OpenClaw"),
        ("routers.deep_scout_router", "Deep Scout (Legacy)"),
        ("routers.scout_unified_router", "ORA Scout (Unified)"),
        ("routers.shannon_router", "Shannon Security (Red Team)"),
        ("routers.db_optimizer_router", "Database Optimizer"),
        ("routers.ora_stream_router", "ORA Streaming (WebSocket + SSE)"),
        ("routers.provisioning_router", "Client Provisioning (Multi-Tenant)"),
        ("routers.system_overview_router", "System Overview (Admin)"),
        ("routers.whatsapp_hybrid_router", "WhatsApp Hybrid (Meta + WHAPI)"),
        ("routers.client_portal_router", "Client Portal (BIN, Onboarding, Activity)"),
        ("routers.news_monitor_router", "News Auto-Monitor"),
        ("routers.shopify_billing_router", "Shopify Billing (Usage-Based)"),
        ("routers.shopify_pulse_router", "Shopify Pulse Scanner & Cart Recovery"),
        ("routers.shopify_oauth_router", "Shopify OAuth & Install"),
        ("routers.root_command_router", "Root Command (Unified Error Intelligence)"),
        ("routers.stem_fix_router", "Stem-Fix (Root-Level Refactor Engine)"),
        ("routers.pillars_map_router", "Pillars Map (3-Level Deep Drill)"),
        ("routers.endpoint_audit_router", "Endpoint Governance / Evidence Classifier"),
        ("routers.deploy_drift_router", "Deploy Drift Monitor"),
        ("routers.autonomous_repair_router", "Autonomous Repair Engine"),
        ("routers.truth_ledger_router", "Truth Ledger (Honesty DNA)"),
        ("routers.a2a_audit_router", "A2A Connectivity Audit"),
        ("routers.sentinel_anomaly_router", "Sentinel Anomaly (iter 285.3)"),
        ("routers.mtth_router", "MTTH & Transparency Wall (iter 285.4)"),
        ("routers.sovereign_node_router", "Sovereign Node & Empire HUD (iter 285.6)"),
        ("routers.master_autopilot_router", "Master Autopilot (iter 285.8)"),
        ("routers.deploy_trigger_router", "Deploy Trigger Webhook (iter 287.1)"),
        ("routers.agent_board_router", "Agent Boardroom / Revenue-Reflector (iter 288.0)"),
        ("routers.admin_founder_customers_router", "Founder Customer Management (iter 288.2)"),
        ("routers.seo_indexnow_router", "SEO IndexNow + Google Sitemap Ping (iter 288.4)"),
        ("routers.sentinel_router", "Autopilot Sentinel Watchdog (iter 288.5)"),
        ("routers.quick_scan_router", "Public Quick Website Scanner (iter 289.8)"),
        ("routers.public_stats_router", "Public AUREM Stats (iter 291)"),
        ("routers.pillars_health_router", "Pillars Health Gate (iter 292)"),
        ("routers.ssot_admin_router", "SSOT Admin Console (iter 294)"),
        ("routers.platform_spine_router", "Platform Spine: A2A+Council+ORA (iter 296)"),
        ("routers.founders_console_router", "Founders Console (iter 296)"),
        ("routers.public_sites_router", "Public AWB Sites (iter 298)"),
        ("routers.customer_edit_router", "Customer DIY Edit Portal (iter 311)"),
        ("routers.domain_router", "Namecheap Domain Reseller (iter 311)"),
        ("routers.ora_dev_actions_router", "ORA Dev Actions Console (iter 281.2 / Phase 2.2)"),
        ("routers.website_repair_router", "Client Website Repair (iter 281.3 / Phase 2.5 preview)"),
        ("routers.public_repair_router", "Public Repair Lead Magnet (iter 281.4 / Phase 2.4)"),
        ("routers.ora_phase_25_router", "ORA Phase 2.5 Customer Handler (iter 281.5)"),
        ("routers.public_ora_demo_router", "Public ORA Demo Chat (iter 281.7)"),
        ("routers.browser_agent_v2_router", "Browser Agent v2 (iter 282e / Phase 2.5F)"),
        ("routers.leads_mining_router", "Leads Email Mining (iter 282g Task 3)"),
        ("routers.lead_assets_router", "Lead Assets (logo upload, iter 282j)"),
        ("routers.admin_daily_log_router", "Admin Daily Log (founder brief audit, iter 282m)"),
        ("routers.me_pwa_router", "ORA PWA — Me Scoped (BIN-based, iter 282o)"),
        ("routers.me_home_router", "ORA PWA — Home Dashboard (iter 322bj)"),
        ("routers.shortlink_router", "Shortlink + Founder Brief Health (iter 282al)"),
        ("routers.seo_router", "SEO / Unlinked Mentions (iter 282al-4)"),
        ("routers.site_qa_router", "Site QA (test-lab.ai, iter 282al-15)"),
        ("routers.council_router", "ORA Council Health (iter 282al-20)"),
        ("routers.ora_brain_router", "ORA Brain / God Mode Health (iter 282al-21)"),
        ("routers.scrapling_router", "Scrapling Health (iter 282al-22)"),
        ("routers.sovereign_truth_router", "Sovereign Truth (iter 282al-26)"),
        ("routers.sms_admin_router", "SMS Admin + CA Allowlist (iter 282al-33)"),
        ("routers.incident_router", "Incident Pipeline (iter 322ff)"),
        ("routers.ora_agent_router", "ORA Autonomous Agent (iter 322fi)"),
        ("routers.ora_attachments_router", "ORA Chat Attachments (iter 327c)"),
        ("routers.ora_github_lock_router", "ORA GitHub Read-Only Lock (iter 327d)"),
        ("routers.ora_lesson_sources_router", "ORA Lesson Sources & Journal (iter 327o+p)"),
        ("routers.pipeda_sla_router",          "PIPEDA + SLA admin (iter 328b+f)"),
        ("routers.uptime_webhook_router",      "External uptime webhook (iter 328c)"),
        ("routers.ora_feedback_router",        "ORA chat feedback (iter 329d)"),
        ("routers.outreach_admin_router",      "Outreach health + manual triggers (iter 330)"),
        ("routers.feature_flags_router",       "Feature Flags admin (iter D-63 zero-downtime)"),
        ("routers.web_search_router",          "Web Search + URL Fetch (iter D-64 Tavily skills)"),
        ("routers.codebase_health_router",     "Codebase Health (iter D-70 live analyzer)"),
        ("routers.poll_cache_stats_router",    "Poll Cache stats + invalidate (iter D-71 perf)"),
        ("routers.scout_autotopup_router",     "Scout Auto-Topup (iter D-71e — keep lead pool above floor)"),
    ]

    for module_path, label in _aurem_with_db:
        if _should_skip(module_path):
            logger.debug(f"[REGISTRY] LEAN skip: {label}")
            continue
        try:
            mod = __import__(module_path, fromlist=["router", "set_db"])
            app.include_router(mod.router)
            if hasattr(mod, "set_db") and db is not None:
                mod.set_db(db)
            # iter 332b D-6 — system_overview_router also exposes a public
            # router via `get_public_router()` (the /share/system-overview
            # mirror at /api/public/system-overview/stats). Mount it too.
            if hasattr(mod, "get_public_router"):
                try:
                    app.include_router(mod.get_public_router())
                except Exception as _pe:
                    logger.warning(f"[REGISTRY] {label} public router error: {_pe}")
            logger.info(f"[REGISTRY] {label} loaded")
        except ImportError as e:
            logger.warning(f"[REGISTRY] {label} not loaded: {e}")
        except Exception as e:
            logger.warning(f"[REGISTRY] {label} error: {e}")

    # iter 322 — One-shot DB migration ops endpoints (founder-only).
    if not _should_skip("routers.db_migrate_router"):
        try:
            from routers.db_migrate_router import router as db_migrate_router, set_db as set_db_migrate_db
            app.include_router(db_migrate_router)
            if db is not None:
                set_db_migrate_db(db)
        except Exception as e:
            logger.warning(f"[REGISTRY] db_migrate_router not loaded: {e}")

    # iter 322 — Hybrid plans + Stripe base-plan checkout
    if not _should_skip("routers.billing_plan_router"):
        try:
            from routers.billing_plan_router import router as billing_plan_router, set_db as set_billing_db
            app.include_router(billing_plan_router)
            if db is not None:
                set_billing_db(db)
            logger.info("[REGISTRY] billing_plan_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] billing_plan_router not loaded: {e}")

    # iter 322 — Admin ORA Q&A across anonymized BIN telemetry
    if not _should_skip("routers.admin_ora_router"):
        try:
            from routers.admin_ora_router import router as admin_ora_router, set_db as set_aora_db
            app.include_router(admin_ora_router)
            if db is not None:
                set_aora_db(db)
            logger.info("[REGISTRY] admin_ora_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] admin_ora_router not loaded: {e}")

    # iter 331c Sprint 6.1 — Consent-based data network (PIPEDA/GDPR).
    if not _should_skip("routers.consent_router"):
        try:
            from routers.consent_router import router as consent_router, set_db as set_consent_db
            app.include_router(consent_router)
            if db is not None:
                set_consent_db(db)
            logger.info("[REGISTRY] consent_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] consent_router not loaded: {e}")

    # iter 331d — Developer Portal foundation (signup/OTP/BYOK/tokens).
    if not _should_skip("routers.developer_portal_router"):
        try:
            from routers.developer_portal_router import (
                router as dev_portal_router, set_db as set_dev_portal_db,
            )
            app.include_router(dev_portal_router)
            if db is not None:
                set_dev_portal_db(db)
                # Ensure Mongo indexes once at startup.
                from services.developer_portal_core import ensure_indexes
                try:
                    import asyncio as _aio
                    _aio.create_task(ensure_indexes())
                except Exception:
                    pass
                # iter 331e — wire dev_security_guards DB for session limits
                try:
                    from services.dev_security_guards import set_db as _set_sec_db
                    _set_sec_db(db)
                except Exception as _sg_e:
                    logger.warning(f"[REGISTRY] dev_security_guards.set_db failed: {_sg_e}")
                # iter 332a-1 — wire validated-solutions cache DB
                try:
                    from services.ora_validated_solutions import set_db as _set_vs_db
                    _set_vs_db(db)
                except Exception as _vs_e:
                    logger.warning(f"[REGISTRY] ora_validated_solutions.set_db failed: {_vs_e}")

                # iter 332a-1 — Specialist Cost Breakdown cockpit endpoint
                try:
                    from routers.ora_specialist_cost_router import (
                        router as _cost_router, set_db as _set_cost_db,
                    )
                    app.include_router(_cost_router)
                    _set_cost_db(db)
                    logger.info("[REGISTRY] ORA Specialist Cost Breakdown endpoint wired")
                except Exception as _cr_e:
                    logger.warning(f"[REGISTRY] specialist-cost router failed: {_cr_e}")

                # iter 332b Batch A — Enterprise router (audit + leads)
                try:
                    from routers.enterprise_router import (
                        router as _ent_router, set_db as _set_ent_db,
                    )
                    app.include_router(_ent_router)
                    _set_ent_db(db)
                    # Ensure indexes for unified_audit_log + enterprise_leads
                    import asyncio as _aio2
                    async def _ent_indexes():
                        try:
                            await db.unified_audit_log.create_index([("timestamp", -1)])
                            await db.unified_audit_log.create_index("event_id", unique=True)
                            await db.unified_audit_log.create_index("user_id")
                            await db.unified_audit_log.create_index("action")
                            await db.enterprise_leads.create_index("created_at")
                            await db.enterprise_leads.create_index("lead_id", unique=True)
                        except Exception as _xe:
                            logger.debug(f"[REGISTRY] enterprise indexes: {_xe}")
                    _aio2.create_task(_ent_indexes())
                    logger.info("[REGISTRY] Enterprise router wired (audit + leads)")
                except Exception as _er_e:
                    logger.warning(f"[REGISTRY] enterprise router failed: {_er_e}")

                # iter 332b Batch B (Step 1) — Organizations router
                try:
                    from routers.organizations_router import (
                        router as _orgs_router, set_db as _set_orgs_db,
                    )
                    app.include_router(_orgs_router)
                    _set_orgs_db(db)
                    logger.info("[REGISTRY] Organizations router wired")
                except Exception as _orgs_e:
                    logger.warning(f"[REGISTRY] organizations router failed: {_orgs_e}")

                # iter 332b Batch B (Step 2) — SAML SSO router
                try:
                    from routers.saml_router import (
                        router as _saml_router, set_db as _set_saml_db,
                    )
                    from services.saml_sp_keys import set_db as _set_spkeys_db
                    app.include_router(_saml_router)
                    _set_saml_db(db)
                    _set_spkeys_db(db)
                    logger.info("[REGISTRY] SAML router wired")
                except Exception as _saml_e:
                    logger.warning(f"[REGISTRY] saml router failed: {_saml_e}")

                # iter 332b Batch B (Step 3) — SCIM router (admin + protocol)
                try:
                    from routers.scim_router import (
                        admin_router as _scim_admin,
                        protocol_router as _scim_proto,
                        set_db as _set_scim_db,
                    )
                    app.include_router(_scim_admin)
                    app.include_router(_scim_proto)
                    _set_scim_db(db)
                    logger.info("[REGISTRY] SCIM routers wired")
                except Exception as _scim_e:
                    logger.warning(f"[REGISTRY] scim router failed: {_scim_e}")

                # iter 332b Batch C — Compliance router (residency + SOC 2 + SLA)
                try:
                    from routers.compliance_router import (
                        router as _comp_router, set_db as _set_comp_db,
                    )
                    app.include_router(_comp_router)
                    _set_comp_db(db)
                    logger.info("[REGISTRY] Compliance router wired")
                except Exception as _comp_e:
                    logger.warning(f"[REGISTRY] compliance router failed: {_comp_e}")

                # iter 332b D-30 — Developer self-deploy + domain linking
                try:
                    from routers.developer_deploy_router import (
                        router as _dep_router, set_db as _set_dep_db,
                    )
                    app.include_router(_dep_router)
                    _set_dep_db(db)
                    logger.info("[REGISTRY] developer_deploy_router wired")
                except Exception as _dep_e:
                    logger.warning(f"[REGISTRY] developer_deploy_router not loaded: {_dep_e}")

                # iter D-33 — AUREM CTO module RE-ENABLED. Mount /aurem-cto/*
                # D-35-deploy-fix — the package lives at
                # /app/backend/aurem_cto/ so the production container
                # (which only ships /app/backend/) can find it.
                # D-38 path-fix — preview cwd is /app, prod cwd is
                # /app/backend; ensure /app/backend is on sys.path so the
                # plain `import aurem_cto` works in BOTH environments.
                try:
                    import sys as _sys, pathlib as _pl
                    _backend_root = _pl.Path(__file__).resolve().parents[1]   # …/backend/routers/registry.py → backend
                    if str(_backend_root) not in _sys.path:
                        _sys.path.insert(0, str(_backend_root))
                    import aurem_cto as _act
                    app.include_router(_act.build_router())
                    _act.set_db(db)
                    logger.info(f"[REGISTRY] aurem_cto module wired (v{_act.VERSION})")
                except Exception as _act_e:
                    import traceback as _tb
                    logger.warning(f"[REGISTRY] aurem_cto module not loaded: "
                                    f"{type(_act_e).__name__}: {_act_e}\n"
                                    f"{_tb.format_exc()[-800:]}")

                # iter D-32 — Onboarding flow (projects + tokens + share + Go-Live)
                try:
                    from routers.onboarding_flow_router import (
                        router as _onb_router,
                        set_db as _set_onb_db,
                        ensure_indexes as _onb_indexes,
                    )
                    app.include_router(_onb_router)
                    _set_onb_db(db)
                    import asyncio as _aio_onb
                    _aio_onb.create_task(_onb_indexes())
                    logger.info("[REGISTRY] onboarding_flow_router wired")
                except Exception as _onb_e:
                    logger.warning(f"[REGISTRY] onboarding_flow_router not loaded: {_onb_e}")

                # iter D-38 — Admin integrations health tracker
                # (read-only dashboard for every 3rd-party API in use)
                try:
                    from routers.admin_integrations_router import (
                        router as _int_router, set_db as _set_int_db,
                    )
                    app.include_router(_int_router)
                    _set_int_db(db)
                    logger.info("[REGISTRY] admin_integrations_router wired")
                except Exception as _int_e:
                    logger.warning(f"[REGISTRY] admin_integrations_router not loaded: {_int_e}")

                # iter D-43 — Founder-controlled platform secrets UI
                # (paste API keys in AUREM, AES-256 stored, applied live
                # to os.environ so existing code paths pick them up).
                try:
                    from routers.platform_secrets_router import (
                        router as _secrets_router,
                        set_db as _set_secrets_db,
                        apply_platform_secrets_to_env,
                    )
                    app.include_router(_secrets_router)
                    _set_secrets_db(db)
                    import asyncio as _aio_secrets
                    _aio_secrets.create_task(apply_platform_secrets_to_env())
                    logger.info("[REGISTRY] platform_secrets_router wired")
                except Exception as _sec_e:
                    logger.warning(f"[REGISTRY] platform_secrets_router not loaded: {_sec_e}")

                # iter D-44 — Database info page (masked Mongo URL)
                try:
                    from routers.developer_database_router import (
                        router as _dbinfo_router,
                    )
                    app.include_router(_dbinfo_router)
                    logger.info("[REGISTRY] developer_database_router wired")
                except Exception as _dbinfo_e:
                    logger.warning(f"[REGISTRY] developer_database_router not loaded: {_dbinfo_e}")

                # iter D-46 — One-click security-key generation + admin
                # panel. Backend mints JWT_SECRET + AUREM_ENCRYPTION_KEY
                # + CORS_ORIGINS, AES-256 stores + applies live to env.
                try:
                    from routers.security_keys_router import (
                        dev_router as _sk_dev_router,
                        admin_router as _sk_admin_router,
                        set_db as _set_sk_db,
                    )
                    app.include_router(_sk_dev_router)
                    app.include_router(_sk_admin_router)
                    _set_sk_db(db)
                    logger.info("[REGISTRY] security_keys_router wired")
                except Exception as _sk_e:
                    logger.warning(f"[REGISTRY] security_keys_router not loaded: {_sk_e}")

                # iter D-73 — Autonomous repair admin queue. D-71p audit
                # found 442 stale `pending_approvals` rows that the
                # repair agent silently couldn't process (legacy schema +
                # test-target Shannon scans). This router lets the
                # founder archive/reject/expire them with a real audit
                # trail. See routers/autonomous_repair_admin_router.py
                try:
                    from routers.autonomous_repair_admin_router import (
                        router as _ara_router,
                        set_db as _set_ara_db,
                    )
                    app.include_router(_ara_router)
                    _set_ara_db(db)
                    logger.info("[REGISTRY] autonomous_repair_admin_router wired")
                except Exception as _ara_e:
                    logger.warning(f"[REGISTRY] autonomous_repair_admin_router not loaded: {_ara_e}")

                # iter D-47 — Save-to-GitHub dialog backend (list repos,
                # list branches, commit manifest + chat history).
                try:
                    from routers.github_save_router import (
                        router as _ghs_router,
                        set_db as _set_ghs_db,
                    )
                    app.include_router(_ghs_router)
                    _set_ghs_db(db)
                    logger.info("[REGISTRY] github_save_router wired")
                except Exception as _ghs_e:
                    logger.warning(f"[REGISTRY] github_save_router not loaded: {_ghs_e}")

                # iter D-48 — cheap /api/version endpoint so the founder
                # can confirm a production deploy actually picked up
                # the latest code.
                try:
                    from routers.version_router import router as _ver_router
                    app.include_router(_ver_router)
                    logger.info("[REGISTRY] version_router wired")
                except Exception as _ver_e:
                    logger.warning(f"[REGISTRY] version_router not loaded: {_ver_e}")

                # iter D-49 — real-execution CTO tools (run-scout, import-leads,
                # run-blast, db-stats). Lets the CTO chat actually DO things
                # instead of only planning.
                try:
                    from routers.cto_tools_router import (
                        router as _cto_tools_router,
                        set_db as _set_cto_tools_db,
                    )
                    if db is not None:
                        _set_cto_tools_db(db)
                    app.include_router(_cto_tools_router)
                    logger.info("[REGISTRY] cto_tools_router wired")
                except Exception as _ctot_e:
                    logger.warning(f"[REGISTRY] cto_tools_router not loaded: {_ctot_e}")

                # iter D-52 — auto-verification (code syntax, GitHub commit,
                # deploy /api/version polling). Replaces CTO's self-reported
                # confirmations with system-level proof.
                try:
                    from routers.cto_verify_router import (
                        router as _cto_verify_router,
                        set_db as _set_cto_verify_db,
                    )
                    if db is not None:
                        _set_cto_verify_db(db)
                    app.include_router(_cto_verify_router)
                    logger.info("[REGISTRY] cto_verify_router wired")
                except Exception as _ctov_e:
                    logger.warning(f"[REGISTRY] cto_verify_router not loaded: {_ctov_e}")

                # iter D-53 — self-learning system. Records only verified
                # outcomes (D-52 gates), surfaces confidence badges, runs
                # a weekly self-review every Sunday 02:00 UTC.
                try:
                    from routers.cto_learning_router import (
                        router as _cto_learning_router,
                        set_db as _set_cto_learning_db,
                    )
                    if db is not None:
                        _set_cto_learning_db(db)
                    app.include_router(_cto_learning_router)
                    logger.info("[REGISTRY] cto_learning_router wired")
                except Exception as _ctol_e:
                    logger.warning(f"[REGISTRY] cto_learning_router not loaded: {_ctol_e}")

                # iter D-54 — real codebase + GitHub access so the CTO
                # chat reads files/commits instead of hallucinating.
                try:
                    from routers.cto_codebase_router import (
                        router as _cto_codebase_router,
                    )
                    app.include_router(_cto_codebase_router)
                    logger.info("[REGISTRY] cto_codebase_router wired")
                except Exception as _ctoc_e:
                    logger.warning(f"[REGISTRY] cto_codebase_router not loaded: {_ctoc_e}")

                # iter D-57 — clean /api/webhooks/resend alias + /api/leads/hot
                # CTO-surfacing endpoint. Reuses lead_lifecycle_router's
                # signature verification (single source of truth).
                try:
                    from routers.resend_webhook_router import (
                        router as _resend_wh_router,
                        set_db as _set_resend_db,
                    )
                    if db is not None:
                        _set_resend_db(db)
                    app.include_router(_resend_wh_router)
                    logger.info("[REGISTRY] resend_webhook_router wired")
                except Exception as _rwh_e:
                    logger.warning(f"[REGISTRY] resend_webhook_router not loaded: {_rwh_e}")

                # iter D-58 — Daily Brief + Template Performance + Proactive ORA
                # admin endpoints. Schedulers wired separately further down.
                try:
                    from routers.cto_brief_router import (
                        router as _cto_brief_router,
                        set_db as _set_cto_brief_db,
                    )
                    if db is not None:
                        _set_cto_brief_db(db)
                    app.include_router(_cto_brief_router)
                    logger.info("[REGISTRY] cto_brief_router wired")
                except Exception as _ctob_e:
                    logger.warning(f"[REGISTRY] cto_brief_router not loaded: {_ctob_e}")

                # iter D-59 — Campaign Health + Autonomous Autofix admin page
                try:
                    from routers.campaign_health_router import (
                        router as _camp_health_router,
                        set_db as _set_camp_db,
                    )
                    if db is not None:
                        _set_camp_db(db)
                    app.include_router(_camp_health_router)
                    logger.info("[REGISTRY] campaign_health_router wired")
                except Exception as _cpe:
                    logger.warning(f"[REGISTRY] campaign_health_router not loaded: {_cpe}")

                # iter D-60 Part B — Public AUREM API + admin key manager
                try:
                    from routers.public_api_router import (
                        router as _pub_api_router,
                        set_db as _set_pub_api_db,
                    )
                    from routers.admin_api_keys_router import (
                        router as _admin_keys_router,
                        set_db as _set_admin_keys_db,
                    )
                    if db is not None:
                        _set_pub_api_db(db)
                        _set_admin_keys_db(db)
                    app.include_router(_pub_api_router)
                    app.include_router(_admin_keys_router)
                    logger.info("[REGISTRY] public_api_router + admin_api_keys_router wired")
                except Exception as _papi_e:
                    logger.warning(f"[REGISTRY] public_api / admin_api_keys not loaded: {_papi_e}")

                # iter D-60 — BugCatch admin bug-report capture
                try:
                    from routers.bug_catch_router import (
                        router as _bug_catch_router,
                        set_db as _set_bug_catch_db,
                    )
                    if db is not None:
                        _set_bug_catch_db(db)
                    app.include_router(_bug_catch_router)
                    logger.info("[REGISTRY] bug_catch_router wired")
                except Exception as _bc_e:
                    logger.warning(f"[REGISTRY] bug_catch_router not loaded: {_bc_e}")

                # iter D-60d — Apollo cost dashboard + budget alert
                try:
                    from routers.apollo_cost_router import (
                        router as _apollo_cost_router,
                        set_db as _set_apollo_cost_db,
                    )
                    from routers.apollo_budget_router import (
                        router as _apollo_budget_router,
                        set_db as _set_apollo_budget_db,
                    )
                    if db is not None:
                        _set_apollo_cost_db(db)
                        _set_apollo_budget_db(db)
                    app.include_router(_apollo_cost_router)
                    app.include_router(_apollo_budget_router)
                    logger.info("[REGISTRY] apollo_cost + apollo_budget routers wired")
                except Exception as _ac_e:
                    logger.warning(f"[REGISTRY] apollo cost/budget not loaded: {_ac_e}")
            logger.info("[REGISTRY] developer_portal_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] developer_portal_router not loaded: {e}")


    # iter 326ff/gg/hh — Phase 3 P3: voice tuning, morning brief, skills marketplace
    if not _should_skip("routers.ora_phase3_router"):
        try:
            from routers.ora_phase3_router import (
                router as ora_phase3_router,
                set_db as set_phase3_db,
            )
            app.include_router(ora_phase3_router)
            if db is not None:
                set_phase3_db(db)
            logger.info("[REGISTRY] ora_phase3_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] ora_phase3_router not loaded: {e}")

    # iter 322r — Autonomous Stack façade for /admin/brain page
    if not _should_skip("routers.autonomous_stack_router"):
        try:
            from routers.autonomous_stack_router import (
                router as autonomous_stack_router,
                set_db as set_autonomous_db,
            )
            app.include_router(autonomous_stack_router)
            if db is not None:
                set_autonomous_db(db)
            logger.info("[REGISTRY] autonomous_stack_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] autonomous_stack_router not loaded: {e}")

    # iter 322v — Deploy-Readiness widget endpoint
    if not _should_skip("routers.deploy_readiness_router"):
        try:
            from routers.deploy_readiness_router import router as deploy_readiness_router
            app.include_router(deploy_readiness_router)
            logger.info("[REGISTRY] deploy_readiness_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] deploy_readiness_router not loaded: {e}")

    # iter 322 — Service gate E2E probe endpoints
    if not _should_skip("routers.gate_test_router"):
        try:
            from routers.gate_test_router import router as gate_test_router
            app.include_router(gate_test_router)
            logger.info("[REGISTRY] gate_test_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] gate_test_router not loaded: {e}")

    # iter 322 — Per-BIN usage breakdown endpoint
    if not _should_skip("routers.usage_router"):
        try:
            from routers.usage_router import router as usage_router, set_db as set_usage_db
            app.include_router(usage_router)
            if db is not None:
                set_usage_db(db)
            logger.info("[REGISTRY] usage_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] usage_router not loaded: {e}")

    # iter 322 — Per-BIN ORA Q&A (customer-facing, strict isolation)
    if not _should_skip("routers.bin_ora_router"):
        try:
            from routers.bin_ora_router import router as bin_ora_router, set_db as set_bin_ora_db
            app.include_router(bin_ora_router)
            if db is not None:
                set_bin_ora_db(db)
            logger.info("[REGISTRY] bin_ora_router loaded")
        except Exception as e:
            logger.warning(f"[REGISTRY] bin_ora_router not loaded: {e}")

    # iter 322 — BIN compound indexes + layer agent A2A subscriptions
    if db is not None:
        try:
            from services.db_indexes import ensure_bin_indexes
            import asyncio as _aio
            _aio.create_task(ensure_bin_indexes(db))
            logger.info("[REGISTRY] BIN compound index ensure dispatched")
        except Exception as e:
            logger.warning(f"[REGISTRY] BIN index ensure failed: {e}")
        try:
            from services.a2a_bus import bus as _a2a
            from services.layer_agents.base import initialize_layer_agents
            initialize_layer_agents(_a2a)
        except Exception as e:
            logger.warning(f"[REGISTRY] layer_agents init skipped: {e}")

    # Panic Takeover (separate from settings)
    if not _should_skip("routers.panic_takeover_router"):
        try:
            from routers.panic_takeover_router import router as panic_takeover_router, set_db as set_panic_takeover_db
            app.include_router(panic_takeover_router)
            if db is not None:
                set_panic_takeover_db(db)
        except Exception:
            pass

    # iter 322 — P1 Mongo pre-warm pinger (anti-flap). Keeps the motor pool
    # hot so Atlas M0 burst-credit throttling never causes cold-start ping
    # spikes that flip the Infrastructure pillar offline.
    if db is not None:
        try:
            from routers.pillars_health_router import start_p1_prewarmer
            start_p1_prewarmer(db)
        except Exception as e:
            logger.warning(f"[REGISTRY] P1 prewarmer not started: {e}")

    # V2V Stream Engine (paired with vapi_voice_router)
    if not _should_skip("routers.v2v_stream_engine"):
        try:
            from routers.v2v_stream_engine import router as v2v_router, set_db as set_v2v_db
            app.include_router(v2v_router)
            if db is not None:
                set_v2v_db(db)
        except Exception:
            pass

    # Shannon Red Team Findings (secondary router from shannon_router)
    try:
        from routers.shannon_router import red_team_router
        app.include_router(red_team_router)
        logger.info("[REGISTRY] Red Team Findings API loaded")
    except Exception as e:
        logger.warning(f"[REGISTRY] Red Team Findings API not loaded: {e}")

    # PentAGI Full Pentest (Enterprise only)
    try:
        from routers.shannon_router import pentagi_router
        from services.pentagi_service import set_db as set_pentagi_db
        app.include_router(pentagi_router)
        if db is not None:
            set_pentagi_db(db)
        logger.info("[REGISTRY] PentAGI Pentest API loaded")
    except Exception as e:
        logger.warning(f"[REGISTRY] PentAGI Pentest API not loaded: {e}")

    # Client Website Intelligence
    if not _should_skip("routers.client_intelligence_router"):
        try:
            from routers.client_intelligence_router import router as intel_router, set_db as set_intel_db
            app.include_router(intel_router)
            if db is not None:
                set_intel_db(db)
        except Exception as e:
            logger.warning(f"[REGISTRY] Client Intelligence router failed: {e}")

    # Voice analytics seeding — DISABLED per user requirement (no mock data in production)
    # To re-enable demo seeding for local dev, set env VOICE_ANALYTICS_SEED=1
    if db is not None and os.environ.get("VOICE_ANALYTICS_SEED") == "1":
        try:
            from routers.voice_analytics_router import seed_voice_calls
            asyncio.ensure_future(seed_voice_calls())
        except Exception:
            pass

    # Create MongoDB performance indexes on startup
    if db is not None:
        try:
            from routers.infra_settings_router import _ensure_indexes
            asyncio.ensure_future(_ensure_indexes(db))
        except Exception:
            pass

    # AUREM Security Modules (not a router, but security init)
    try:
        from utils.aurem_secrets import init_aurem_security
        from utils.aurem_rate_limiter import set_db as set_rate_limiter_db
        from utils.aurem_jwt import set_db as set_jwt_db
        from utils.aurem_rls import set_db as set_rls_db
        from utils.aurem_security_middleware import set_db as set_security_mw_db
        init_aurem_security(strict=False)
        if db is not None:
            set_rate_limiter_db(db)
            set_jwt_db(db)
            set_rls_db(db)
            set_security_mw_db(db)
    except ImportError:
        pass

    # AUREM AI Chat Router
    if not _should_skip("routers.aurem_ai_router"):
        try:
            from routers.aurem_ai_router import router as aurem_ai_router, set_db as set_aurem_ai_db
            set_aurem_ai_db(db)  # iter 322eb — enable llm_response_cache writes
            app.include_router(aurem_ai_router)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # SECTION 4: API-prefixed routers
    # ═══════════════════════════════════════════
    _api_prefixed_try = [
        ("routers.rag_router", "RAG Knowledge"),
        ("routers.batch_router", "Batch Tracking"),
        ("routers.ai_email_router", "AI Email"),
        ("routers.whatsapp_alerts", "WhatsApp Alerts"),
        ("routers.biometric_auth", "Biometric Auth"),
        ("routers.github_integration", "GitHub Integration"),
    ]
    for module_path, label in _api_prefixed_try:
        if _should_skip(module_path):
            logger.debug(f"[REGISTRY] LEAN skip: {label}")
            continue
        try:
            mod = __import__(module_path, fromlist=["router", "set_db"])
            app.include_router(mod.router, prefix="/api")
            if hasattr(mod, "set_db") and db:
                mod.set_db(db)
            logger.info(f"[REGISTRY] {label} loaded")
        except ImportError as e:
            logger.warning(f"[REGISTRY] {label} not loaded: {e}")

    # Biometric Secure (WebAuthn/FIDO2)
    if not _should_skip("routers.biometric_secure"):
        try:
            from routers.biometric_secure import router as biometric_secure_router
            app.include_router(biometric_secure_router)
        except Exception:
            pass

    # PWA Router
    if not _should_skip("routers.pwa_router"):
        try:
            from routers.pwa_router import router as pwa_router
            app.include_router(pwa_router)
        except Exception:
            pass

    # Push Notification Router
    if not _should_skip("routers.push_notification_router"):
        try:
            from routers.push_notification_router import router as push_router, set_db as set_push_db
            app.include_router(push_router)
            if db is not None:
                set_push_db(db)
        except Exception:
            pass

    # System Pulse
    if not _should_skip("routers.system_pulse_router"):
        try:
            from routers.system_pulse_router import router as pulse_router, set_db as set_pulse_db
            app.include_router(pulse_router)
            if db is not None:
                set_pulse_db(db)
        except Exception:
            pass

    # Site Monitor (Customer-facing SKU + free lead magnet — iter 257)
    if not _should_skip("routers.site_monitor_router"):
        try:
            from routers.site_monitor_router import router as site_monitor_router, set_db as set_sm_db
            app.include_router(site_monitor_router)
            if db is not None:
                set_sm_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] site_monitor_router skipped: {e}")

    # QA Bot (Hybrid System Pulse + Deep QA Agent)
    if not _should_skip("routers.qa_bot_router"):
        try:
            from routers.qa_bot_router import router as qa_bot_router, set_db as set_qa_db
            app.include_router(qa_bot_router)
            if db is not None:
                set_qa_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] qa_bot_router skipped: {e}")

    # Sovereign Memory Guard (iter 322k — two-stamp learning gate)
    if not _should_skip("routers.sovereign_memory_router"):
        try:
            from routers.sovereign_memory_router import (
                router as sovereign_memory_router,
                set_db as set_sov_mem_db,
            )
            app.include_router(sovereign_memory_router)
            if db is not None:
                set_sov_mem_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] sovereign_memory_router skipped: {e}")

    # Sovereign Telemetry (iter 322m — single-pulse aggregator for the dashboard)
    if not _should_skip("routers.sovereign_telemetry_router"):
        try:
            from routers.sovereign_telemetry_router import (
                router as sovereign_telemetry_router,
                set_db as set_sov_tel_db,
            )
            app.include_router(sovereign_telemetry_router)
            if db is not None:
                set_sov_tel_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] sovereign_telemetry_router skipped: {e}")

    # Public Sovereign-Status (iter 322m Day 5+ — sales-leverage trust badge)
    if not _should_skip("routers.public_status_router"):
        try:
            from routers.public_status_router import (
                router as public_status_router,
                set_db as set_pub_status_db,
            )
            app.include_router(public_status_router)
            if db is not None:
                set_pub_status_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] public_status_router skipped: {e}")

    # ORA Support Widget endpoint (iter 322o — persistent draggable helper)
    if not _should_skip("routers.ora_support_router"):
        try:
            from routers.ora_support_router import (
                router as ora_support_router,
                set_db as set_ora_support_db,
            )
            app.include_router(ora_support_router)
            if db is not None:
                set_ora_support_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_support_router skipped: {e}")

    # Total-Scout Source Attribution (iter 322n — multi-source discovery telemetry)
    if not _should_skip("routers.scout_sources_router"):
        try:
            from routers.scout_sources_router import (
                router as scout_sources_router,
                set_db as set_scout_sources_db,
            )
            app.include_router(scout_sources_router)
            if db is not None:
                set_scout_sources_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] scout_sources_router skipped: {e}")

    # Customer Scout Run (gated /api/scout/run — dogfood + dashboard entry point)
    if not _should_skip("routers.scout_run_router"):
        try:
            from routers.scout_run_router import router as scout_run_router
            app.include_router(scout_run_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] scout_run_router skipped: {e}")


    # Dogfood Pulse — 14d health snapshot for BIN AUR-FNDR-001
    if not _should_skip("routers.dogfood_pulse_router"):
        try:
            from routers.dogfood_pulse_router import (
                router as dogfood_pulse_router,
                set_db as set_dogfood_pulse_db,
            )
            app.include_router(dogfood_pulse_router)
            if db is not None:
                set_dogfood_pulse_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] dogfood_pulse_router skipped: {e}")


    # Customer Results + Inbox (Tiles A/B/C + /api/customer/inbox/*)
    if not _should_skip("routers.customer_results_router"):
        try:
            from routers.customer_results_router import (
                router as customer_results_router,
                set_db as set_customer_results_db,
            )
            app.include_router(customer_results_router)
            if db is not None:
                set_customer_results_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] customer_results_router skipped: {e}")


    # BIN Intelligence (Pixel/Invoice/Mobile/Unified Merge — Parts 1,3,4,5,7)
    if not _should_skip("routers.customer_intelligence_router"):
        try:
            from routers.customer_intelligence_router import (
                router as customer_intelligence_router,
                set_db as set_intelligence_db,
            )
            app.include_router(customer_intelligence_router)
            if db is not None:
                set_intelligence_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] customer_intelligence_router skipped: {e}")


    # Admin BIN Detail (right-panel enhanced view + manual promote)
    if not _should_skip("routers.admin_bin_detail_router"):
        try:
            from routers.admin_bin_detail_router import (
                router as admin_bin_detail_router,
                set_db as set_admin_bin_detail_db,
            )
            app.include_router(admin_bin_detail_router)
            if db is not None:
                set_admin_bin_detail_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] admin_bin_detail_router skipped: {e}")


    # ORA Skills Router (markdown skill library exposure + health)
    if not _should_skip("routers.ora_skills_router"):
        try:
            from routers.ora_skills_router import router as ora_skills_router
            app.include_router(ora_skills_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_skills_router skipped: {e}")


    # Antigravity Skills Router (1,453+ playbooks + broadcast to 28 agents)
    if not _should_skip("routers.antigravity_skills_router"):
        try:
            from routers.antigravity_skills_router import (
                router as antigravity_skills_router,
                set_db as set_antigravity_skills_db,
            )
            set_antigravity_skills_db(db)
            app.include_router(antigravity_skills_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] antigravity_skills_router skipped: {e}")

    # iter R234c — Security Patterns Router (AUREM-SEC-PATTERNS-V1)
    # 15 detect-regex patterns derived from 45 audited bugs (R2-R8).
    # Exposes /api/admin/sec-patterns/{,/playbook,/scan,/scan-paths}.
    # NOTE: prefix is `sec-patterns` (NOT `security-patterns`) so the
    # LEAN-mode prune list doesn't strip it via the `/api/admin/security`
    # prefix-match in _registry_lean_prune.py.
    if not _should_skip("routers.security_patterns_router"):
        try:
            from routers.security_patterns_router import (
                router as security_patterns_router,
                set_db as set_security_patterns_db,
            )
            set_security_patterns_db(db)
            app.include_router(security_patterns_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] security_patterns_router skipped: {e}")

    # iter 322ep — Design Extract admin router (DTCG/shadcn tokens from competitor URLs)
    if not _should_skip("routers.design_extract_router"):
        try:
            from routers.design_extract_router import router as design_extract_router
            app.include_router(design_extract_router)
            logger.info("[REGISTRY] design_extract_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] design_extract_router skipped: {e}")

    # iter 322es — ORA Rollback (one-click restore from safe_edit backups)
    if not _should_skip("routers.ora_rollback_router"):
        try:
            from routers.ora_rollback_router import router as ora_rollback_router
            app.include_router(ora_rollback_router)
            logger.info("[REGISTRY] ora_rollback_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_rollback_router skipped: {e}")

    # iter 322es — ORA Settings (founder-facing platform settings)
    if not _should_skip("routers.ora_settings_router"):
        try:
            from routers.ora_settings_router import router as ora_settings_router
            app.include_router(ora_settings_router)
            logger.info("[REGISTRY] ora_settings_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_settings_router skipped: {e}")

    # iter 322es — ORA Files (multi-format upload + analyze)
    if not _should_skip("routers.ora_files_router"):
        try:
            from routers.ora_files_router import router as ora_files_router
            app.include_router(ora_files_router)
            logger.info("[REGISTRY] ora_files_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_files_router skipped: {e}")

    # iter 322er — Git Commit Gate (founder approves every ORA commit)
    if not _should_skip("routers.git_gate_router"):
        try:
            from routers.git_gate_router import router as git_gate_router
            app.include_router(git_gate_router)
            logger.info("[REGISTRY] git_gate_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] git_gate_router skipped: {e}")

    # iter 322eq — ORA CTO Cockpit (council history + cost + quotas)
    if not _should_skip("routers.ora_cto_cockpit_router"):
        try:
            from routers.ora_cto_cockpit_router import router as ora_cto_cockpit_router
            app.include_router(ora_cto_cockpit_router)
            logger.info("[REGISTRY] ora_cto_cockpit_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_cto_cockpit_router skipped: {e}")

    # iter 322ep — ORA Optimize admin router (codeburn-pattern LLM budget watchdog)
    if not _should_skip("routers.ora_optimize_router"):
        try:
            from routers.ora_optimize_router import router as ora_optimize_router
            app.include_router(ora_optimize_router)
            logger.info("[REGISTRY] ora_optimize_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_optimize_router skipped: {e}")



    # Customer Site Audit Router ($49/mo SEO + Ads Waste detector)
    if not _should_skip("routers.customer_audit_router"):
        try:
            from routers.customer_audit_router import (
                router as customer_audit_router,
                set_db as set_customer_audit_db,
                set_jwt as set_customer_audit_jwt,
            )
            set_customer_audit_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_customer_audit_jwt(JWT_SECRET, JWT_ALGORITHM)
            app.include_router(customer_audit_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] customer_audit_router skipped: {e}")

    # iter 322eh — DB Audit Router (5-layer hygiene scan for ORA/admin)
    if not _should_skip("routers.db_audit_router"):
        try:
            from routers.db_audit_router import (
                router as db_audit_router, set_db as set_db_audit_db,
            )
            set_db_audit_db(db)
            app.include_router(db_audit_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] db_audit_router skipped: {e}")

    # iter 322ej — ORA Tools Router (read-only investigation hands for ORA)
    if not _should_skip("routers.ora_tools_router"):
        try:
            from routers.ora_tools_router import (
                router as ora_tools_router, set_db as set_ora_tools_db,
            )
            set_ora_tools_db(db)
            app.include_router(ora_tools_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_tools_router skipped: {e}")

    # iter 322el — ORA Chat Router (tool-grounded conversational endpoint)
    if not _should_skip("routers.ora_chat_router"):
        try:
            from routers.ora_chat_router import (
                router as ora_chat_router, set_db as set_ora_chat_db,
            )
            set_ora_chat_db(db)
            app.include_router(ora_chat_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_chat_router skipped: {e}")

    # iter 322ey — Founder Saves Audit Router (unified ledger view)
    if not _should_skip("routers.founder_saves_router"):
        try:
            from routers.founder_saves_router import (
                router as founder_saves_router, set_db as set_founder_saves_db,
            )
            set_founder_saves_db(db)
            app.include_router(founder_saves_router)
            logger.info("[REGISTRY] founder_saves_router loaded")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] founder_saves_router skipped: {e}")


    # Memoir Router (Git-versioned semantic memory for 28 agents + ORA)
    # Production-safety: skip if MEMOIR_SKIP=1 or /app/data is read-only.
    # The CLI `memoir new` exits 5 on K8s overlay FS and the registry call
    # is synchronous → can stall startup if it retries. Make it best-effort
    # and respect the operator's MEMOIR_SKIP=1 override.
    if not _should_skip("routers.memoir_router") and os.environ.get("MEMOIR_SKIP", "").strip() not in ("1", "true", "yes", "on"):
        try:
            from routers.memoir_router import router as memoir_router
            from services import memoir_service
            memoir_service.init()
            app.include_router(memoir_router)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] memoir_router skipped: {e}")


    # Dev Stack Health (Pillars Map green/red grid)
    if not _should_skip("routers.dev_stack_health_router"):
        try:
            from routers.dev_stack_health_router import (
                router as dev_stack_health_router,
                set_db as set_dev_stack_db,
            )
            app.include_router(dev_stack_health_router)
            if db is not None:
                set_dev_stack_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] dev_stack_health_router skipped: {e}")


    # Blast-Chain (Section 7 — staggered 4-touch chains + reply webhook)
    if not _should_skip("routers.blast_chain_router"):
        try:
            from routers.blast_chain_router import (
                router as blast_chain_router,
                admin_router as blast_chain_admin_router,
                set_db as set_blast_chain_db,
            )
            app.include_router(blast_chain_router)
            app.include_router(blast_chain_admin_router)
            if db is not None:
                set_blast_chain_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] blast_chain_router skipped: {e}")

    # Council Backlog (Phase 2 — clear-backlog + auto-promote endpoints)
    if not _should_skip("routers.council_backlog_router"):
        try:
            from routers.council_backlog_router import (
                router as council_backlog_router,
                set_db as set_council_backlog_db,
            )
            app.include_router(council_backlog_router)
            if db is not None:
                set_council_backlog_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] council_backlog_router skipped: {e}")

    # ORA Knowledge (Phase 3 — Tier-3 query + digest + assessment)
    if not _should_skip("routers.ora_knowledge_router"):
        try:
            from routers.ora_knowledge_router import (
                router as ora_knowledge_router,
                set_db as set_ora_knowledge_db,
            )
            app.include_router(ora_knowledge_router)
            if db is not None:
                set_ora_knowledge_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] ora_knowledge_router skipped: {e}")

    # Sentinel Client (iter 258c — client-side error capture + AI diagnose)
    if not _should_skip("routers.sentinel_client_router"):
        try:
            from routers.sentinel_client_router import router as sentinel_client_router, set_db as set_sentinel_db
            app.include_router(sentinel_client_router)
            if db is not None:
                set_sentinel_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] sentinel_client_router skipped: {e}")

    # Graphify Knowledge Graph + Shareable snapshots (iter 261)
    if not _should_skip("routers.graphify_router"):
        try:
            from routers.graphify_router import router as graphify_router, set_db as set_graphify_db
            app.include_router(graphify_router)
            if db is not None:
                set_graphify_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] graphify_router skipped: {e}")

    # Admin Links Hub (iter 262) — aggregated URL dashboard
    if not _should_skip("routers.admin_links_router"):
        try:
            from routers.admin_links_router import router as admin_links_router, set_db as set_links_db
            app.include_router(admin_links_router)
            if db is not None:
                set_links_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] admin_links_router skipped: {e}")

    # Case Study Builder (iter 258d — board-ready PDF reports, dual mode)
    if not _should_skip("routers.case_study_router"):
        try:
            from routers.case_study_router import router as case_study_router, set_db as set_cs_db
            app.include_router(case_study_router)
            if db is not None:
                set_cs_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] case_study_router skipped: {e}")

    # Hunter Live Test (iter 258f — safe E2E diagnostic: sends 1 mock lead email to admin)
    if not _should_skip("routers.hunter_test_router"):
        try:
            from routers.hunter_test_router import router as hunter_test_router, set_db as set_ht_db
            app.include_router(hunter_test_router)
            if db is not None:
                set_ht_db(db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"[REGISTRY] hunter_test_router skipped: {e}")

    # Tenant Migration
    if not _should_skip("routers.tenant_migration_router"):
        try:
            from routers.tenant_migration_router import router as tenant_migration_router
            app.include_router(tenant_migration_router)
        except Exception:
            pass

    # Nexus Hub
    if not _should_skip("routers.nexus_router"):
        try:
            from routers.nexus_router import router as nexus_router, set_db as set_nexus_db
            app.include_router(nexus_router)
            if db is not None:
                set_nexus_db(db)
        except Exception:
            pass

    # La Vela Bianca — REMOVED (iter 322ar cleanup: not part of AUREM product)

    # Crypto Signal Engine — REMOVED (iter 322ar cleanup: AUREM is a business
    # automation platform; crypto treasury was the wrong product surface)

    # Live Sync
    if not _should_skip("routers.live_sync_router"):
        try:
            from routers.live_sync_router import router as live_sync_router
            app.include_router(live_sync_router)
        except Exception:
            pass

    # Z-Image-Turbo
    if not _should_skip("routers.z_image_router"):
        try:
            from routers.z_image_router import router as z_image_router
            app.include_router(z_image_router)
        except Exception:
            pass

    # AUREM Redis
    if not _should_skip("routers.aurem_redis_router"):
        try:
            from routers.aurem_redis_router import router as aurem_redis_router
            app.include_router(aurem_redis_router)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # SECTION 5: Direct-import routers (always load)
    # ═══════════════════════════════════════════
    _direct_routers = [
        ("routers.integration_api", "External Integration API", None),
        ("routers.customer_scanner", "Customer Scanner", None),
        ("routers.live_scanner", "Live Scanner", None),
        ("routers.ora_repair_engine", "ORA Repair Engine", None),
        ("routers.ai_repair_router", "AI Repair", None),
        ("routers.v2_customer_actions_router", "V2 Customer Actions", None),
        ("routers.customer_pipeline_router", "Customer Pipeline", None),
        ("routers.seo_funnel_router", "SEO Funnel (public revenue)", None),
        ("routers.system_health_full_router", "System Health Composite", None),
        ("routers.intelligence_router", "Intelligence", None),
        ("routers.voice_sales_agent", "Voice Sales Agent", None),
        ("routers.invisible_coach", "Invisible Coach", None),
        ("routers.sales_pipeline", "Sales Pipeline", None),
        ("routers.local_llm_router", "Local LLM", None),
        ("routers.resend_domain_router", "Resend Domain", None),
        ("routers.omnichannel_hub", "Omnichannel Hub", None),
        ("routers.hermes_router", "Hermes Identity", None),
        ("routers.graphify_router", "Graphify Knowledge Graph", None),
        ("routers.bitnet_router", "BitNet Worker", None),
        ("routers.swarm_router", "A2A Swarm", None),
        ("routers.sovereign_voice_router", "Sovereign Voice", None),
        ("routers.attribution_engine", "Attribution Engine", None),
        ("routers.tenant_customers_router", "Tenant Customers", None),
        ("routers.enrichment_service", "Enrichment Service", None),
        ("routers.crm_sync_engine", "CRM Sync Engine", None),
        ("routers.recovery_comms_router", "Recovery Comms", None),
        ("routers.infra_settings_router", "Infrastructure Settings", None),
        ("routers.github_deploy_router", "GitHub Deploy", None),
        ("routers.robotics_router", "Robotics Digital Twin", None),
        ("routers.voicebox_router", "Voicebox Sovereign Voice", None),
        ("routers.free_api_router", "Free API Arsenal", None),
        ("routers.social_media_router", "Social Media (Envoy)", None),
        ("routers.content_engine_router", "Content Engine", None),
        ("routers.forensic_miner_router", "Forensic Miner", None),
        ("routers.mmx_router", "MMX Multimodal", None),
        ("routers.tier1_router", "Tier 1 Upgrades", None),
        ("routers.document_skills_router", "Document Skills", None),
        ("routers.video_engine_router", "Video Engine", None),
        ("routers.autonomy_router", "Autonomous Operations", None),
        ("routers.skills_router", "Skills & Tools", None),
    ]
    for module_path, label, prefix in _direct_routers:
        if _should_skip(module_path):
            logger.debug(f"[REGISTRY] LEAN skip: {label}")
            continue
        try:
            mod = __import__(module_path, fromlist=["router", "set_db"])
            if prefix:
                app.include_router(mod.router, prefix=prefix)
            else:
                app.include_router(mod.router)
            if hasattr(mod, "set_db") and db:
                mod.set_db(db)
            # Also handle set_db_ref for local_llm_router
            if hasattr(mod, "set_db_ref") and db:
                mod.set_db_ref(db)
        except Exception as e:
            logger.warning(f"[REGISTRY] {label} not loaded: {e}")

    # Admin Cache Router
    if not _should_skip("routers.admin_cache_router"):
        try:
            from routers.admin_cache_router import router as admin_cache_router
            app.include_router(admin_cache_router)
        except Exception:
            pass

    # Acquisition Engine
    if not _should_skip("routers.acquisition_router"):
        try:
            from routers.acquisition_router import router as acquisition_router, set_db as set_acquisition_db
            app.include_router(acquisition_router)
            if db is not None:
                set_acquisition_db(db)
        except Exception:
            pass

    # Viral Gate (Social Share Unlock)
    if not _should_skip("routers.viral_gate_router"):
        try:
            from routers.viral_gate_router import router as viral_gate_router, set_db as set_vg_db
            app.include_router(viral_gate_router)
            if db is not None:
                set_vg_db(db)
        except Exception:
            pass

    # Proximity Blast (Geofenced Lead Discovery)
    if not _should_skip("routers.proximity_blast_router"):
        try:
            from routers.proximity_blast_router import router as proximity_router, set_db as set_prox_db
            app.include_router(proximity_router)
            if db is not None:
                set_prox_db(db)
        except Exception:
            pass

    # Global Pulse (World-Sense Intelligence)
    if not _should_skip("routers.global_pulse_router"):
        try:
            from routers.global_pulse_router import router as global_pulse_router, set_db as set_gp_db
            app.include_router(global_pulse_router)
            if db is not None:
                set_gp_db(db)
        except Exception:
            pass

    # Legal Documents
    if not _should_skip("routers.legal_router"):
        try:
            from routers.legal_router import router as legal_router, set_db as set_legal_db, seed_legal_documents
            app.include_router(legal_router)
            if db is not None:
                set_legal_db(db)
                import asyncio as _legal_asyncio
                _legal_asyncio.get_event_loop().create_task(seed_legal_documents())
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # SECTION 5.5: Business ID + ORA Context + Notifications
    # ═══════════════════════════════════════════
    if not _should_skip("routers.business_id_router"):
        try:
            from routers.business_id_router import router as biz_id_router, set_db as set_biz_id_db
            app.include_router(biz_id_router)
            if db is not None:
                set_biz_id_db(db)
        except Exception:
            pass

    if not _should_skip("routers.ora_context_router"):
        try:
            from routers.ora_context_router import router as ora_ctx_router, set_db as set_ora_ctx_db
            app.include_router(ora_ctx_router)
            if db is not None:
                set_ora_ctx_db(db)
        except Exception:
            pass

    try:
        from services.notification_triggers import set_db as set_notif_db
        if db is not None:
            set_notif_db(db)
    except Exception:
        pass

    try:
        from services.welcome_package import set_db as set_welcome_db
        if db is not None:
            set_welcome_db(db)
    except Exception:
        pass

    if not _should_skip("routers.admin_business_id_router"):
        try:
            from routers.admin_business_id_router import router as admin_bid_router, set_db as set_admin_bid_db
            app.include_router(admin_bid_router)
            if db is not None:
                set_admin_bid_db(db)
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # SECTION 5.6: BIN Auth (First-login, WhatsApp OTP, Admin search)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.bin_auth_router"):
        try:
            from routers.bin_auth_router import router as bin_auth_router, set_db as set_bin_auth_db
            app.include_router(bin_auth_router)
            if db is not None:
                set_bin_auth_db(db)
            logger.info("[REGISTRY] BIN Auth router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] BIN Auth router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.7: Customer Portal (Website, Reviews, Social, Reports, Billing, Referrals)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.customer_portal_router"):
        try:
            from routers.customer_portal_router import router as customer_portal_router, set_db as set_customer_portal_db
            app.include_router(customer_portal_router)
            if db is not None:
                set_customer_portal_db(db)
            logger.info("[REGISTRY] Customer Portal router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Customer Portal router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.8: Pixel Patches (live-patch engine for aurem-pixel.js)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.pixel_patches_router"):
        try:
            from routers.pixel_patches_router import router as pixel_patches_router, set_db as set_pixel_patches_db
            app.include_router(pixel_patches_router)
            if db is not None:
                set_pixel_patches_db(db)
            logger.info("[REGISTRY] Pixel Patches router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Pixel Patches router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.9: Deep Scanner API (exposes utils/deep_scanner.py)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.deep_scan_router"):
        try:
            from routers.deep_scan_router import router as deep_scan_router, set_db as set_deep_scan_db
            app.include_router(deep_scan_router)
            if db is not None:
                set_deep_scan_db(db)
            logger.info("[REGISTRY] Deep Scanner router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Deep Scanner router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.10: Customer Tokens + Monthly Report
    # ═══════════════════════════════════════════
    if not _should_skip("routers.customer_tokens_router"):
        try:
            from routers.customer_tokens_router import router as tokens_router, set_db as set_tokens_db
            app.include_router(tokens_router)
            if db is not None:
                set_tokens_db(db)
            logger.info("[REGISTRY] Customer Tokens router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Customer Tokens router failed: {e}")

    try:
        from services.customer_monthly_report import set_db as set_monthly_report_db
        from services.google_places_sync import set_db as set_places_db
        if db is not None:
            set_monthly_report_db(db)
            set_places_db(db)
    except Exception as e:
        logger.warning(f"[REGISTRY] Monthly report / Places wiring failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.11: Smart Onboarding (auto-detect + one-click start)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.smart_onboarding_router"):
        try:
            from routers.smart_onboarding_router import router as onb_router, set_db as set_onb_db
            app.include_router(onb_router)
            if db is not None:
                set_onb_db(db)
            logger.info("[REGISTRY] Smart Onboarding router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Smart Onboarding router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.12: System Audit (Iteration 202 — Living Audit Dashboard)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.system_audit_router"):
        try:
            from routers.system_audit_router import router as audit_router, set_db as set_audit_db
            app.include_router(audit_router)
            if db is not None:
                set_audit_db(db)
            logger.info("[REGISTRY] System Audit router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] System Audit router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.13: Stripe Embedded Checkout (Apple Pay one-tap)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.stripe_embed_router"):
        try:
            from routers.stripe_embed_router import router as se_router, set_db as set_se_db
            app.include_router(se_router)
            if db is not None:
                set_se_db(db)
            logger.info("[REGISTRY] Stripe Embedded Checkout router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Stripe Embedded router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.14: Wiring Audit (Iteration 203 — automated feature checklist)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.wiring_audit_router"):
        try:
            from routers.wiring_audit_router import router as wa_router, set_db as set_wa_db
            app.include_router(wa_router)
            if db is not None:
                set_wa_db(db)
            logger.info("[REGISTRY] Wiring Audit router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Wiring Audit router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.15: Admin Financials (Apple Pay txns + HST)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.admin_financials_router"):
        try:
            from routers.admin_financials_router import router as af_router, set_db as set_af_db
            app.include_router(af_router)
            if db is not None:
                set_af_db(db)
            logger.info("[REGISTRY] Admin Financials router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Admin Financials router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.17: Customer 360 View (Iteration 208)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.customer_360_router"):
        try:
            from routers.customer_360_router import router as c360_router, set_db as set_c360_db
            app.include_router(c360_router)
            if db is not None:
                set_c360_db(db)
            logger.info("[REGISTRY] Customer 360 router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Customer 360 router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.18: Customer 360 Action Panel (Iteration 209)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.customer_360_actions_router"):
        try:
            from routers.customer_360_actions_router import router as c360a_router, set_db as set_c360a_db
            app.include_router(c360a_router)
            if db is not None:
                set_c360a_db(db)
            logger.info("[REGISTRY] Customer 360 Actions router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Customer 360 Actions router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.19: Customer Diagnostics + Auto-Repair Pipeline
    # ═══════════════════════════════════════════
    if not _should_skip("routers.customer_diagnostic_router"):
        try:
            from routers.customer_diagnostic_router import (
                router as cdiag_router,
                set_db as set_cdiag_db,
            )
            app.include_router(cdiag_router)
            if db is not None:
                set_cdiag_db(db)
            logger.info("[REGISTRY] Customer Diagnostic router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Customer Diagnostic router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.20: Emergency Admin Password Reset (bootstrap, secret-gated)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.emergency_reset_router"):
        try:
            from routers.emergency_reset_router import (
                router as emerg_router, set_db as set_emerg_db,
            )
            app.include_router(emerg_router)
            if db is not None:
                set_emerg_db(db)
            logger.info("[REGISTRY] Emergency Reset router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Emergency Reset router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.21: Outreach Dedup (P0 cost-saver — stops duplicate SMS/WA)
    # ═══════════════════════════════════════════
    if not _should_skip("routers.outreach_dedup_router"):
        try:
            from routers.outreach_dedup_router import (
                router as odd_router, set_db as set_odd_db,
            )
            app.include_router(odd_router)
            if db is not None:
                set_odd_db(db)
            # Also wire the service-layer db handle (for the chokepoint funcs)
            try:
                from services.outreach_dedup import set_db as set_dedup_service_db
                set_dedup_service_db(db)
            except Exception:
                pass
            logger.info("[REGISTRY] Outreach Dedup router registered")
        except Exception as e:
            logger.warning(f"[REGISTRY] Outreach Dedup router failed: {e}")

    # ═══════════════════════════════════════════
    # SECTION 5.16: DB Index Builder (Iteration 205 — safe-mode, add-only)
    # ═══════════════════════════════════════════
    if db is not None:
        try:
            import asyncio as _idx_asyncio
            from services.db_index_builder import build_all_indexes

            # Stash result on app.state so /api/admin/db-indexes/status can surface it
            app.state.db_index_result = {"status": "building"}

            async def _build_indexes_bg():
                try:
                    res = await build_all_indexes(db)
                    app.state.db_index_result = res
                except Exception as e:
                    logger.warning(f"[REGISTRY] Index builder background failed: {e}")
                    app.state.db_index_result = {"status": "failed", "error": str(e)[:200]}

            _idx_asyncio.get_event_loop().create_task(_build_indexes_bg())
            logger.info("[REGISTRY] DB Index builder scheduled (background)")
        except Exception as e:
            logger.warning(f"[REGISTRY] DB Index builder setup failed: {e}")

    # Assign Business ID to existing AUREM tenant if missing
    try:
        if db is not None:
            import asyncio as _bid_asyncio
            async def _assign_reroots_bid():
                try:
                    from routers.business_id_router import ensure_business_id
                    reroots = await db.users.find_one({"email": "pawandeep19may1985@gmail.com"}, {"_id": 0})
                    if reroots and not reroots.get("business_id"):
                        bid = await ensure_business_id(reroots)
                        logger.info(f"[REGISTRY] Assigned Business ID {bid} to AUREM tenant")
                except Exception as ex:
                    logger.warning(f"[REGISTRY] AUREM BID assignment: {ex}")
            _bid_asyncio.get_event_loop().create_task(_assign_reroots_bid())
    except Exception as e:
        logger.warning(f"[REGISTRY] AUREM BID startup: {e}")

    # ═══════════════════════════════════════════
    # SECTION 6: APScheduler (Bug Engine)
    # ═══════════════════════════════════════════
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.executors.asyncio import AsyncIOExecutor
        from apscheduler.executors.pool import ThreadPoolExecutor
        from utils.aurem_bug_engine import scheduled_bug_scan
        from utils.self_scan import run_self_scan

        aurem_scheduler = AsyncIOScheduler(
            # iter 325t — production thread starvation fix.
            #
            # Symptom on aurem.live: repeating warnings ──
            #   "Execution of job X skipped: maximum number of running
            #    instances reached (1)"
            #   "Run time of job Y was missed by 0:01:01"
            #
            # Root cause: default APScheduler ThreadPoolExecutor has only
            # 10 workers. We schedule ~50 background jobs (probes,
            # watchdogs, scans, repairs). When a few I/O-bound jobs (HTTP
            # probes, Mongo aggregates, LLM calls) block for 30-60s, the
            # whole pool stalls and *every* other job misses its next
            # tick. Compounds quickly.
            #
            # Fix: dedicated `AsyncIOExecutor` (default) for async
            # coroutines + a 30-worker `ThreadPoolExecutor` for legacy
            # sync jobs. Async jobs no longer compete with sync I/O for
            # threads — coroutines yield naturally during awaits. With
            # 30 threads + the async loop, a single slow probe no longer
            # cascades into 5-job misses.
            executors={
                "default":     AsyncIOExecutor(),
                "threadpool":  ThreadPoolExecutor(max_workers=30),
            },
            job_defaults={
                "max_instances": 1,
                "coalesce": True,
                # iter 325t — bumped 30 → 90s. The old window caused
                # *every* slow tick to register as a "missed by 0:01:00"
                # warning since most probes naturally take 5-20s. 90s
                # tolerates real pod-warm-up + Atlas reconnects without
                # spamming logs.
                "misfire_grace_time": 90,
            }
        )
        # Expose at module level so /api/admin/system-audit can introspect job list + next-run times
        globals()["aurem_scheduler"] = aurem_scheduler
        aurem_scheduler.add_job(
            scheduled_bug_scan,
            IntervalTrigger(minutes=10),
            id='aurem_bug_scan',
            name='AUREM Bug Engine Scan',
            replace_existing=True
        )

        # Agent A2A self-heal — detects wedged ORA agents (boot-stuck like
        # "boot-1777956593 · 52m") and runs the 3-step heal cascade
        # (heartbeat ping → A2A signal → pulse log). Default scan every 60s
        # so the per-tick fan-out (~30 Mongo lookups) cannot starve the K8s
        # `/health` probe during deploy cold-boot. iter 322o.
        try:
            from datetime import datetime as _dt, timedelta as _td, timezone as _tz
            from services.agent_wedge_detector import (
                run_wedge_scan as _run_wedge_scan,
                WEDGE_SCAN_INTERVAL_S as _WEDGE_INTERVAL,
            )
            async def _wedge_job():
                try:
                    return await _run_wedge_scan(db)
                except Exception as _e:
                    logger.warning(f"[wedge-detector] scan error: {_e}")
            # Cold-boot grace: skip the first 45 s after pod start so the
            # K8s liveness probe locks in 200s before any heavy worker
            # competes for the event loop.
            _wedge_first_run = _dt.now(_tz.utc) + _td(seconds=45)
            aurem_scheduler.add_job(
                _wedge_job,
                IntervalTrigger(
                    seconds=max(int(_WEDGE_INTERVAL), 300),  # iter 323c — floor at 5min to prevent pile-up
                    start_date=_wedge_first_run,
                    jitter=60,
                ),
                id='agent_wedge_scan',
                name='Agent A2A Self-Heal Loop',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info(
                f"[scheduler] agent_wedge_scan scheduled every {_WEDGE_INTERVAL}s "
                f"(first run at {_wedge_first_run.isoformat()})"
            )
        except Exception as _w_err:
            logger.warning(f"[scheduler] agent_wedge_scan not scheduled: {_w_err}")

        # iter 322p — FollowUp ORA tick (every 30 min): nudges silent leads
        try:
            from services.followup_ora_engine import run_followup_tick as _run_followup
            async def _followup_job():
                try:
                    return await _run_followup(db)
                except Exception as _e:
                    logger.warning(f"[followup-ora] tick error: {_e}")
            aurem_scheduler.add_job(
                _followup_job,
                IntervalTrigger(minutes=30),
                id='followup_ora_tick',
                name='FollowUp ORA Silent-Lead Nurture',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            logger.info("[scheduler] followup_ora_tick scheduled every 30min")
        except Exception as _e:
            logger.warning(f"[scheduler] followup_ora_tick not scheduled: {_e}")

        # iter 322p — Referral ORA tick (every 6 h): asks happy customers
        try:
            from services.referral_ora_engine import run_referral_tick as _run_referral
            async def _referral_job():
                try:
                    return await _run_referral(db)
                except Exception as _e:
                    logger.warning(f"[referral-ora] tick error: {_e}")
            aurem_scheduler.add_job(
                _referral_job,
                IntervalTrigger(hours=6),
                id='referral_ora_tick',
                name='Referral ORA Customer Harvest',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            logger.info("[scheduler] referral_ora_tick scheduled every 6h")
        except Exception as _e:
            logger.warning(f"[scheduler] referral_ora_tick not scheduled: {_e}")

        # iter 322p — Council Verdict Auto-Apply (every 5 min): runs the
        # safe-action allowlist on promoted learnings carrying a
        # `recommended_fix` field. Closes the self-evolving loop.
        try:
            from services.council_verdict_executor import (
                run_verdict_executor_tick as _run_verdict,
            )
            async def _verdict_job():
                try:
                    return await _run_verdict(db)
                except Exception as _e:
                    logger.warning(f"[verdict-exec] tick error: {_e}")
            aurem_scheduler.add_job(
                _verdict_job,
                IntervalTrigger(minutes=5),
                id='council_verdict_executor',
                name='Council Verdict Auto-Apply',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            logger.info("[scheduler] council_verdict_executor scheduled every 5min")
        except Exception as _e:
            logger.warning(f"[scheduler] council_verdict_executor not scheduled: {_e}")

        # Daily self-scan of aurem.live at 3:00 AM EST (dogfooding)
        aurem_scheduler.add_job(
            run_self_scan,
            CronTrigger(hour=3, minute=0, timezone="America/Toronto"),
            id='aurem_self_daily_scan',
            name='AUREM Self-Client Daily Scan',
            replace_existing=True
        )
        logger.info("[REGISTRY] Self-scan cron scheduled: daily at 3:00 AM EST")

        # Daily Disaster Recovery: mirror primary → secondary Atlas cluster.
        # Runs at 03:00 UTC (low-traffic window). Skipped silently if
        # SECONDARY_MONGO_URL is not configured.
        try:
            from services.db_backup_service import run_backup_async
            aurem_scheduler.add_job(
                run_backup_async,
                CronTrigger(hour=3, minute=0, timezone="UTC"),
                id='aurem_dr_backup_daily',
                name='AUREM DR Backup (Primary → Secondary)',
                kwargs={'triggered_by': 'scheduler_cron'},
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("[REGISTRY] DR backup cron scheduled: daily at 03:00 UTC")
        except Exception as _e:
            logger.warning(f"[REGISTRY] DR backup cron failed to register: {_e}")

        # iter 331d — Developer Portal sandbox cleanup (45-day idle gc).
        # Walks /tmp/ora-sandbox-* and deletes folders untouched for
        # ORA_SANDBOX_INACTIVE_DAYS days. Runs daily at 04:30 UTC.
        try:
            from services.developer_portal_core import cleanup_inactive_sandboxes
            async def _sandbox_cleanup_tick():
                try:
                    r = await cleanup_inactive_sandboxes()
                    if r.get("removed"):
                        logger.info(
                            f"[sandbox-cleanup] removed {r['removed']} stale sandboxes "
                            f"(scanned {r.get('scanned', 0)})"
                        )
                except Exception as _ce:
                    logger.warning(f"[sandbox-cleanup] tick error: {_ce}")
            aurem_scheduler.add_job(
                _sandbox_cleanup_tick,
                CronTrigger(hour=4, minute=30, timezone="UTC"),
                id='aurem_dev_sandbox_cleanup',
                name='Developer Sandbox Cleanup (45d idle)',
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("[REGISTRY] Dev sandbox cleanup cron scheduled: daily at 04:30 UTC")
        except Exception as _e:
            logger.warning(f"[REGISTRY] Dev sandbox cleanup cron failed: {_e}")

        # iter 331e — Developer Portal email sequence (Day 3 / 7 / 25).
        # Daily at 05:00 UTC walks verified developer accounts, classifies
        # each into 0..N pending email buckets, sends via Resend, stamps
        # `email_sequence_sent[<bucket>]` so we never re-fire.
        try:
            from services.developer_email_sequence import (
                run_sequence_tick, set_db as _set_seq_db,
            )
            if db is not None:
                _set_seq_db(db)
            async def _email_sequence_tick():
                try:
                    r = await run_sequence_tick()
                    if r.get("sent"):
                        logger.info(
                            f"[dev-email-seq] sent={r['sent']} "
                            f"scanned={r['scanned']} skipped={r['skipped']} "
                            f"failed={r['failed']}"
                        )
                except Exception as _ee:
                    logger.warning(f"[dev-email-seq] tick error: {_ee}")
            aurem_scheduler.add_job(
                _email_sequence_tick,
                CronTrigger(hour=5, minute=0, timezone="UTC"),
                id='aurem_dev_email_sequence',
                name='Developer Onboarding Email Sequence (Day 3/7/25)',
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("[REGISTRY] Dev email sequence cron scheduled: daily at 05:00 UTC")
        except Exception as _e:
            logger.warning(f"[REGISTRY] Dev email sequence cron failed: {_e}")

        # Midnight daily usage reset for tenant_customers
        async def reset_tenant_daily_usage():
            try:
                from datetime import datetime as _dt, timezone as _tz
                async for cust in db.tenant_customers.find({}, {"_id": 0, "tenant_id": 1, "usage.actions_limit": 1}):
                    limit = cust.get("usage", {}).get("actions_limit", 500)
                    await db.tenant_customers.update_one(
                        {"tenant_id": cust["tenant_id"]},
                        {"$set": {
                            "usage.actions_used": 0,
                            "usage.actions_remaining": limit,
                            "usage.pipeline_runs_today": 0,
                            "usage.last_reset_date": _dt.now(_tz.utc).isoformat(),
                        }}
                    )
                logger.info("[SCHEDULER] Daily tenant usage reset completed")
            except Exception as ue:
                logger.warning(f"[SCHEDULER] Usage reset error: {ue}")

        aurem_scheduler.add_job(
            reset_tenant_daily_usage,
            CronTrigger(hour=0, minute=0, timezone="America/Toronto"),
            id='tenant_daily_usage_reset',
            name='Tenant Daily Usage Reset',
            replace_existing=True
        )
        logger.info("[REGISTRY] Daily usage reset cron scheduled: midnight EST")

        # ── Drip Sequencer — every 6 hours (Task 2: Lead Lifecycle) ──
        try:
            from services.drip_sequencer import run_due_drips as _run_drips
            async def _drip_tick():
                try:
                    result = await _run_drips(db)
                    if result.get("executed"):
                        logger.info(f"[DRIP] {result['executed']} drip step(s) executed")
                except Exception as e:
                    logger.warning(f"[DRIP] tick error: {e}")

            aurem_scheduler.add_job(
                _drip_tick,
                IntervalTrigger(hours=6),
                id='lifecycle_drip_sequencer',
                name='Lead Lifecycle: Drip Sequencer (6h)',
                replace_existing=True,
            )
            logger.info("[REGISTRY] Drip sequencer cron scheduled: every 6 hours")
        except Exception as e:
            logger.warning(f"[REGISTRY] Drip sequencer cron failed to register: {e}")

        # ── ORA Self-Heal Watchdog — every 5 minutes (iter 281.1) ──
        try:
            from services.ora_self_heal import install_scheduler as _install_oh
            _install_oh(aurem_scheduler, db)
        except Exception as e:
            logger.warning(f"[REGISTRY] ORA Self-Heal watchdog failed to register: {e}")

        # ── Renewal Nudge — daily 09:00 UTC (iter 332b D-1) ──
        try:
            from services.renewal_nudges import install_scheduler as _install_renewal
            _install_renewal(aurem_scheduler, db)
        except Exception as e:
            logger.warning(f"[REGISTRY] Renewal nudge cron failed to register: {e}")

        # ── Morning Digest — 7 AM EST daily ──
        try:
            from services.morning_digest import send_morning_digest as _send_digest
            async def _digest_tick():
                try:
                    result = await _send_digest(db)
                    logger.info(f"[DIGEST] Morning digest sent={result.get('sent')} to={result.get('to')}")
                except Exception as e:
                    logger.warning(f"[DIGEST] tick error: {e}")

            aurem_scheduler.add_job(
                _digest_tick,
                CronTrigger(hour=7, minute=0, timezone="America/Toronto"),
                id='morning_digest_7am',
                name='AUREM Morning Digest (7 AM EST)',
                replace_existing=True,
            )
            logger.info("[REGISTRY] Morning digest cron scheduled: 7 AM EST daily")
        except Exception as e:
            logger.warning(f"[REGISTRY] Morning digest cron failed: {e}")

        # ── Campaign Automation Scheduler ──
        try:
            from routers.campaign_router import (
                run_daily_scrape, run_website_scans,
                run_email_sequence, run_whatsapp_sequence,
            )

            # iter D-71 — auto_blast_scheduler() is launched by
            # pillars/sales/worker.py at startup (the p1-worker). Verified
            # by '[p1-worker] ✓ Auto-Blast scheduler attached' in the boot
            # log. The cron jobs below are SEPARATE daily fixed-time
            # triggers; the per-cycle blast loop runs every N min on its
            # own from p1-worker.

            # Daily 9 AM EST — Scout scrapes new businesses
            aurem_scheduler.add_job(
                run_daily_scrape,
                CronTrigger(hour=14, minute=0, timezone="UTC"),  # 9 AM EST = 14 UTC
                id='campaign_daily_scrape',
                name='Campaign: Daily Lead Scrape',
                replace_existing=True,
            )

            # Daily 10 AM EST — Auto scan new lead websites
            aurem_scheduler.add_job(
                run_website_scans,
                CronTrigger(hour=15, minute=0, timezone="UTC"),  # 10 AM EST = 15 UTC
                id='campaign_website_scan',
                name='Campaign: Website Scanning',
                replace_existing=True,
            )

            # Daily 2 PM EST — Email outreach
            aurem_scheduler.add_job(
                run_email_sequence,
                CronTrigger(hour=19, minute=0, timezone="UTC"),  # 2 PM EST = 19 UTC
                id='campaign_email_sequence',
                name='Campaign: Email Sequence',
                replace_existing=True,
            )

            # Daily 10:00 UTC — Second-chance outreach for refunded leads
            # (iter 282al-17). Sends $297 manual-repair offer 14 days after
            # a $197 auto-repair was refunded.
            try:
                from services.second_chance_service import run_second_chance_outreach as _run_sc
                async def _sc_job():
                    try:
                        return await _run_sc(db)
                    except Exception as _e:
                        logger.warning(f"[second-chance] job error: {_e}")
                aurem_scheduler.add_job(
                    _sc_job,
                    CronTrigger(hour=10, minute=0, timezone="UTC"),
                    id='second_chance_outreach',
                    name='Second-Chance Outreach (refunded → $297 manual)',
                    replace_existing=True,
                )
                logger.info("[scheduler] second_chance_outreach scheduled daily 10:00 UTC")
            except Exception as _sc_err:
                logger.warning(f"[scheduler] second_chance_outreach not scheduled: {_sc_err}")

            # Daily 02:30 UTC — ORA self-training (iter 282al-21)
            try:
                from services.ora_god_mode import ora_self_training as _run_train
                async def _train_job():
                    try:
                        return await _run_train(db)
                    except Exception as _e:
                        logger.warning(f"[ora-self-training] job error: {_e}")
                aurem_scheduler.add_job(
                    _train_job,
                    CronTrigger(hour=2, minute=30, timezone="UTC"),
                    id='ora_self_training',
                    name='ORA Self-Training (analyze brain_sessions → improve skills)',
                    replace_existing=True,
                )
                logger.info("[scheduler] ora_self_training scheduled daily 02:30 UTC")
            except Exception as _e:
                logger.warning(f"[scheduler] ora_self_training not scheduled: {_e}")

            # Weekly Sunday 03:00 UTC — ORA Knowledge Snapshot Builder (iter 282al-23)
            try:
                from services.ora_knowledge_builder import build_knowledge_snapshot as _run_snapshot
                async def _snapshot_job():
                    try:
                        out = await _run_snapshot(db)
                        logger.info(f"[ora-knowledge-builder] snapshot built: {out}")
                        return out
                    except Exception as _e:
                        logger.warning(f"[ora-knowledge-builder] job error: {_e}")
                aurem_scheduler.add_job(
                    _snapshot_job,
                    CronTrigger(day_of_week='sun', hour=3, minute=0, timezone="UTC"),
                    id='ora_knowledge_builder',
                    name='ORA Knowledge Builder (weekly snapshot synth)',
                    replace_existing=True,
                )
                logger.info("[scheduler] ora_knowledge_builder scheduled Sunday 03:00 UTC")
            except Exception as _e:
                logger.warning(f"[scheduler] ora_knowledge_builder not scheduled: {_e}")

            # Every 6 h — Scrapling Warmup (iter 282al-23)
            try:
                from services.scrapling_warmup import run_scrapling_warmup as _run_warmup
                async def _warmup_job():
                    try:
                        # Hard cap 4 minutes so a stuck Playwright session
                        # cannot block subsequent jobs on the same scheduler.
                        out = await asyncio.wait_for(
                            _run_warmup(db, max_domains=100, concurrency=4),
                            timeout=240.0,
                        )
                        logger.info(f"[scrapling-warmup] periodic warm: {out.get('warmed')}/{out.get('considered')}")
                        return out
                    except asyncio.TimeoutError:
                        logger.warning("[scrapling-warmup] periodic warm timed out (240s)")
                    except Exception as _e:
                        logger.warning(f"[scrapling-warmup] job error: {_e}")
                aurem_scheduler.add_job(
                    _warmup_job,
                    IntervalTrigger(hours=6),
                    id='scrapling_warmup',
                    name='Scrapling Warmup (top-100 domains, every 6h)',
                    replace_existing=True,
                )
                logger.info("[scheduler] scrapling_warmup scheduled every 6h")
            except Exception as _e:
                logger.warning(f"[scheduler] scrapling_warmup not scheduled: {_e}")

            # Daily 4 PM EST — WhatsApp outreach (re-enabled per user request)
            aurem_scheduler.add_job(
                run_whatsapp_sequence,
                CronTrigger(hour=21, minute=0, timezone="UTC"),
                id='campaign_whatsapp_sequence',
                name='Campaign: WhatsApp Sequence',
                replace_existing=True,
            )

            logger.info("[REGISTRY] Campaign automation scheduler started (9AM scrape, 10AM scan, 2PM email, 4PM WhatsApp)")

            # ── iter 282m — Founder Daily Brief (Push + EOD email, NO WhatsApp) ──
            try:
                from services.founder_daily_brief import (
                    set_db as _set_brief_db,
                    push_morning_armed as _push_morning_armed,
                    push_scout_complete as _push_scout_complete,
                    push_architect_complete as _push_architect_complete,
                    push_envoy_complete as _push_envoy_complete,
                    push_midday_check as _push_midday_check,
                    send_end_of_day_email as _send_eod_email,
                )
                _set_brief_db(db)

                # 9:00 AM EST — morning armed push (just before scrape kicks off)
                aurem_scheduler.add_job(
                    _push_morning_armed,
                    CronTrigger(hour=9, minute=0, timezone="America/Toronto"),
                    id='brief_morning_armed',
                    name='Founder Brief: Morning Armed Push',
                    replace_existing=True,
                )
                # 9:30 AM EST — Scout-complete push (30 min after 9 AM scrape starts)
                aurem_scheduler.add_job(
                    _push_scout_complete,
                    CronTrigger(hour=9, minute=30, timezone="America/Toronto"),
                    id='brief_scout_complete',
                    name='Founder Brief: Scout Complete Push',
                    replace_existing=True,
                )
                # 10:30 AM EST — Architect-complete push (30 min after 10 AM scan)
                aurem_scheduler.add_job(
                    _push_architect_complete,
                    CronTrigger(hour=10, minute=30, timezone="America/Toronto"),
                    id='brief_architect_complete',
                    name='Founder Brief: Architect Complete Push',
                    replace_existing=True,
                )
                # 2:30 PM EST — Envoy-complete push (30 min after 2 PM email)
                aurem_scheduler.add_job(
                    _push_envoy_complete,
                    CronTrigger(hour=14, minute=30, timezone="America/Toronto"),
                    id='brief_envoy_complete',
                    name='Founder Brief: Envoy Complete Push',
                    replace_existing=True,
                )
                # 1:00 PM EST — Midday check
                aurem_scheduler.add_job(
                    _push_midday_check,
                    CronTrigger(hour=13, minute=0, timezone="America/Toronto"),
                    id='brief_midday_check',
                    name='Founder Brief: Midday Check Push',
                    replace_existing=True,
                )
                # 6:00 PM EST — End-of-day email (single source of truth)
                aurem_scheduler.add_job(
                    _send_eod_email,
                    CronTrigger(hour=18, minute=0, timezone="America/Toronto"),
                    id='brief_end_of_day_email',
                    name='Founder Brief: End-of-Day Email',
                    replace_existing=True,
                )
                logger.info("[REGISTRY] Founder Daily Brief cron scheduled "
                            "(9 AM armed, 9:30 scout, 10:30 architect, 1 PM midday, "
                            "2:30 envoy, 6 PM EOD email)")
                # iter 282u — print next-run-time per job for visibility
                try:
                    for jid in ('brief_morning_armed', 'brief_scout_complete',
                                'brief_architect_complete', 'brief_midday_check',
                                'brief_envoy_complete', 'brief_end_of_day_email'):
                        j = aurem_scheduler.get_job(jid)
                        if j and j.next_run_time:
                            logger.info(f"[REGISTRY]   {jid}: next_run={j.next_run_time.isoformat()}")
                except Exception:
                    pass
            except Exception as fbe:
                logger.warning(f"[REGISTRY] Founder Daily Brief cron failed: {fbe}")

            # ── iter 282al-10 — Hourly Self-Audit cron + Pillars chip ──
            try:
                from services.self_audit import (
                    ensure_self_audit_indexes, run_self_audit,
                )
                # iter D-65 — AsyncIOScheduler MUST receive a coroutine
                # function + args, not a lambda that returns the
                # coroutine. A returned coroutine is never awaited →
                # `RuntimeWarning: coroutine 'run_self_audit' was never
                # awaited` and the audit never runs.
                aurem_scheduler.add_job(
                    run_self_audit,
                    CronTrigger(minute=5, timezone="America/Toronto"),
                    args=[db],
                    id='self_audit_hourly',
                    name='Self-Audit: aurem.live every hour @ :05',
                    replace_existing=True,
                    max_instances=1,
                )
                import asyncio as _aio_sa
                _aio_sa.get_event_loop().create_task(
                    ensure_self_audit_indexes(db),
                )
                logger.info("[REGISTRY] Self-Audit cron scheduled (every hour at :05 EDT)")
            except Exception as sae:
                logger.warning(f"[REGISTRY] Self-Audit cron failed: {sae}")

            # ── iter D-70 — Codebase Health analyzer (every 6h + boot) ──
            try:
                from services.codebase_health import run_snapshot as _ch_run_snapshot
                from services.codebase_health import set_db as _ch_set_db
                _ch_set_db(db)
                aurem_scheduler.add_job(
                    _ch_run_snapshot,
                    CronTrigger(hour='*/6', minute=10, timezone='UTC'),
                    id='codebase_health_6h',
                    name='Codebase Health snapshot every 6h',
                    replace_existing=True,
                    max_instances=1,
                )
                # Boot snapshot: ASAP so the dashboard has data right after boot.
                aurem_scheduler.add_job(
                    _ch_run_snapshot,
                    'date',
                    id='codebase_health_boot',
                    name='Codebase Health: boot snapshot',
                    replace_existing=True,
                    misfire_grace_time=120,
                )
                logger.info("[REGISTRY] Codebase Health scheduler armed (boot + 6h)")
            except Exception as _che:
                logger.warning(f"[REGISTRY] Codebase Health setup failed: {_che}")

            # ── iter 282r — Trial SMS Reminders (A2P 10DLC live) ──
            # 10:00 AM America/Toronto daily — fires welcome (Day 1),
            # ending_soon (T-1 day), and last_day (T-0) in one pass.
            try:
                from services.trial_sms_reminders import run_trial_sms_reminders
                aurem_scheduler.add_job(
                    run_trial_sms_reminders,
                    CronTrigger(hour=10, minute=0, timezone="America/Toronto"),
                    args=[db],
                    id='trial_sms_reminders',
                    name='Trial SMS Reminders: Day 1 / Ending Soon / Last Day',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] Trial SMS reminders scheduled (10:00 AM EST daily)")
            except Exception as tse:
                logger.warning(f"[REGISTRY] Trial SMS reminder scheduler failed: {tse}")

            # ── iter 282x — Campaign Daily Brief (Resend email, 9 PM EDT) ──
            # Glanceable end-of-day KPI snapshot sent to founder.
            try:
                from services.campaign_daily_brief import send_campaign_daily_brief
                aurem_scheduler.add_job(
                    send_campaign_daily_brief,
                    CronTrigger(hour=21, minute=0, timezone="America/Toronto"),
                    args=[db],
                    id='campaign_daily_brief',
                    name='Campaign Daily Brief (9 PM EDT email)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] Campaign Daily Brief scheduled (9:00 PM EST daily → founder email)")
            except Exception as cbe:
                logger.warning(f"[REGISTRY] Campaign Daily Brief scheduler failed: {cbe}")

            # ── iter 282af — webclaw_usage daily rollup (2 AM UTC) ──
            try:
                from services.webclaw_usage_rollup import run_daily_rollup
                aurem_scheduler.add_job(
                    run_daily_rollup,
                    CronTrigger(hour=2, minute=0, timezone="UTC"),
                    args=[db],
                    id='webclaw_usage_rollup',
                    name='webclaw_usage → webclaw_usage_daily (2 AM UTC)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] webclaw_usage daily rollup scheduled (2 AM UTC)")
            except Exception as rre:
                logger.warning(f"[REGISTRY] webclaw rollup scheduler failed: {rre}")

            # ── iter 282ag — Active Site Watcher (Saturday 7 AM UTC) ──
            try:
                from services.site_change_watcher import run_weekly_site_watch
                aurem_scheduler.add_job(
                    run_weekly_site_watch,
                    CronTrigger(day_of_week='sat', hour=7, minute=0, timezone="UTC"),
                    args=[db],
                    id='site_change_watcher',
                    name='Active Site Watcher (Saturday 7 AM UTC)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] Active Site Watcher scheduled (Saturday 7 AM UTC)")
            except Exception as scw:
                logger.warning(f"[REGISTRY] Site Change Watcher scheduler failed: {scw}")

            # ── iter 282ah — Daily Priority Watcher (Mon-Fri 6 AM UTC) ──
            try:
                from services.site_change_watcher import run_daily_priority_watch
                aurem_scheduler.add_job(
                    run_daily_priority_watch,
                    CronTrigger(day_of_week='mon-fri', hour=6, minute=0,
                                 timezone="UTC"),
                    args=[db],
                    id='site_change_priority_daily',
                    name='Daily Priority Site Watcher (Mon-Fri 6 AM UTC)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] Daily Priority Site Watcher scheduled (Mon-Fri 6 AM UTC)")
            except Exception as pds:
                logger.warning(f"[REGISTRY] Daily Priority Watcher failed: {pds}")

            # ── iter 282ah — One-off schema drift migration (idempotent) ──
            try:
                from services.schema_migrations import fix_schema_drift
                import asyncio as _aio
                async def _run_migration():
                    res = await fix_schema_drift(db)
                    logger.info(f"[REGISTRY] schema_migrations.fix_schema_drift → {res}")
                _aio.get_event_loop().create_task(_run_migration())
            except Exception as sme:
                logger.warning(f"[REGISTRY] schema_migrations dispatch failed: {sme}")

            # ── iter 282ai — composer cache TTL indexes ──
            try:
                from services.outreach_composer import ensure_cache_indexes
                import asyncio as _aio2
                _aio2.get_event_loop().create_task(ensure_cache_indexes(db))
            except Exception as cce:
                logger.debug(f"[REGISTRY] composer cache index dispatch failed: {cce}")

            # ── iter 282al-7 — CASL value-first TTL indexes ──
            try:
                from services.outreach_composer import ensure_casl_indexes
                import asyncio as _aio2c
                _aio2c.get_event_loop().create_task(ensure_casl_indexes(db))
            except Exception as cce:
                logger.debug(f"[REGISTRY] casl index dispatch failed: {cce}")

            # ── iter 282al-8 — ORA Widget Chat (Prompt 10) ──
            try:
                from routers.widget_chat_router import (
                    router as widget_router,
                    set_db as set_widget_db,
                    ensure_widget_indexes,
                )
                set_widget_db(db)
                app.include_router(widget_router)
                import asyncio as _aio_wgt
                _aio_wgt.get_event_loop().create_task(
                    ensure_widget_indexes(db),
                )
                logger.info("ORA Widget Chat router registered")
            except Exception as wge:
                logger.warning(f"Widget Chat router not loaded: {wge}")

            # ── iter 282al-8 — PRD Auto-Fill (Prompt 11) ──
            try:
                from routers.prd_autofill_router import (
                    router as prd_router,
                    set_db as set_prd_db,
                )
                set_prd_db(db)
                app.include_router(prd_router)
                logger.info("PRD Auto-Fill router registered")
            except Exception as prde:
                logger.warning(f"PRD Auto-Fill router not loaded: {prde}")

            # ── iter 282al-9 — Inbound Reply Handler (auto-warm-reply) ──
            try:
                from routers.inbound_email_router import (
                    router as inbound_router,
                    set_db as set_inbound_db,
                )
                from services.inbound_reply_handler import ensure_inbound_indexes
                set_inbound_db(db)
                app.include_router(inbound_router)
                import asyncio as _aio_inb
                _aio_inb.get_event_loop().create_task(
                    ensure_inbound_indexes(db),
                )
                logger.info("Inbound Reply Handler router registered")
            except Exception as inbe:
                logger.warning(f"Inbound Reply Handler router not loaded: {inbe}")

            # ── iter 282al-10 — Self-Audit chip router ──
            try:
                from routers.self_audit_router import (
                    router as self_audit_router,
                    set_db as set_self_audit_db,
                )
                set_self_audit_db(db)
                app.include_router(self_audit_router)
                logger.info("Self-Audit router registered")
            except Exception as sae:
                logger.warning(f"Self-Audit router not loaded: {sae}")

            # ── iter 282al-10 — Scheduler introspection ──
            try:
                from routers.scheduler_introspect_router import (
                    router as sched_router,
                )
                app.include_router(sched_router)
                logger.info("Scheduler introspect router registered")
            except Exception as sie:
                logger.warning(f"Scheduler introspect router not loaded: {sie}")

            # ── iter 282aj — LinkedIn weekly tip (Monday 9 AM UTC) ──
            try:
                from services.linkedin_publisher import weekly_linkedin_tip
                aurem_scheduler.add_job(
                    weekly_linkedin_tip,
                    CronTrigger(day_of_week='mon', hour=9, minute=0, timezone="UTC"),
                    args=[db],
                    id='linkedin_weekly_tip',
                    name='LinkedIn Weekly Tip (Monday 9 AM UTC)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] LinkedIn Weekly Tip scheduled (Monday 9 AM UTC)")
            except Exception as lwt:
                logger.warning(f"[REGISTRY] LinkedIn Weekly Tip failed: {lwt}")

            # ── iter 282ak — ORA Skill Learner (2 AM UTC) ──
            try:
                from services.skill_learner import run_learning_cycle
                # iter D-65 — same fix as Self-Audit: pass coroutine
                # function + args, not a lambda. Lambda returned the
                # coroutine without awaiting → cycle never ran.
                aurem_scheduler.add_job(
                    run_learning_cycle,
                    CronTrigger(hour=2, minute=15, timezone="UTC"),
                    args=[db],
                    id='skill_learning_cycle',
                    name='ORA Skill Learner (2:15 AM UTC, 15min after Learning Bus)',
                    replace_existing=True,
                    max_instances=1,
                )
                logger.info("[REGISTRY] ORA Skill Learner scheduled (2:15 AM UTC)")
            except Exception as sle:
                logger.warning(f"[REGISTRY] Skill Learner failed: {sle}")

            # ── iter 282af — one-off TTL indexes + 90-day purge on boot ──
            try:
                from services.site_change_watcher import ensure_trigger_indexes
                from services.website_diff import init_indexes_and_cleanup
                import asyncio as _aio
                async def _init_all():
                    await init_indexes_and_cleanup(db)
                    await ensure_trigger_indexes(db)
                _aio.get_event_loop().create_task(_init_all())
                logger.info("[REGISTRY] website_diff + site_change_watcher indexes dispatched")
            except Exception as wde:
                logger.warning(f"[REGISTRY] website_diff init dispatch failed: {wde}")

            # ── iter 282al — Shortlink + 7 orphan TTL indexes ──
            try:
                from services.shortlink_service import ensure_shortlink_indexes
                from services.unlinked_mentions_service import ensure_mention_indexes
                import asyncio as _aio3
                async def _shortlink_and_ttls():
                    await ensure_shortlink_indexes(db)
                    await ensure_mention_indexes(db)
                    # iter 282al-6 — dedup + DNC indexes
                    try:
                        from services.lead_dedup import ensure_dedup_indexes
                        await ensure_dedup_indexes(db)
                    except Exception as _de:
                        logger.debug(f"[REGISTRY] dedup index init: {_de}")
                    # Seven orphan collections flagged in CATCH-UP audit.
                    # Each needs a TTL on `ts` to prevent unbounded growth.
                    ttl_plan = [
                        ("composer_fallbacks",    "ts", 30  * 24 * 3600),
                        ("skill_invocations",     "ts", 30  * 24 * 3600),
                        ("skill_learnings",       "ts", 180 * 24 * 3600),
                        ("skill_route_cache",     "ts",  1  * 24 * 3600),
                        ("linkedin_oauth_states", "ts",  1  * 3600),
                        ("shortlink_clicks",      "ts", 90  * 24 * 3600),
                        ("scout_rejected",        "ts",  7  * 24 * 3600),
                    ]
                    for coll, field, secs in ttl_plan:
                        try:
                            await db[coll].create_index(
                                [(field, 1)],
                                expireAfterSeconds=secs,
                                name=f"{field}_ttl",
                            )
                        except Exception as _te:
                            logger.debug(f"[REGISTRY] TTL skip {coll}.{field}: {_te}")
                    logger.info("[REGISTRY] Shortlink + 7 orphan TTL indexes dispatched")
                _aio3.get_event_loop().create_task(_shortlink_and_ttls())
            except Exception as _sle:
                logger.warning(f"[REGISTRY] Shortlink/TTL init dispatch failed: {_sle}")

            # ── iter 282al — Founder Morning Brief cron (daily 7 AM America/Toronto = 12:00 UTC STD / 11:00 UTC DST) ──
            try:
                from services.morning_brief import run_morning_brief
                # APScheduler converts the timezone at schedule time — we
                # lock to the configured TZ so DST transitions don't drift
                # the fire time.
                aurem_scheduler.add_job(
                    run_morning_brief,
                    CronTrigger(hour=7, minute=0, timezone="America/Toronto"),
                    id='founder_morning_brief',
                    name='Founder Morning Brief (7:00 AM America/Toronto)',
                    replace_existing=True,
                    max_instances=1,
                    misfire_grace_time=3600,  # fire within 1h of scheduled time after downtime
                )
                logger.info("[REGISTRY] Founder Morning Brief scheduled (7:00 AM America/Toronto)")

                # Boot-time catch-up: if no brief fired in the last 24h,
                # fire one on startup so the health chip leaves red.
                import asyncio as _aio4
                async def _boot_catchup_brief():
                    try:
                        from datetime import datetime as _dt, timezone as _tz
                        latest = await db.morning_briefs.find_one(
                            {}, sort=[("generated_at", -1)],
                            projection={"_id": 0, "generated_at": 1},
                        )
                        should_fire = True
                        if latest and latest.get("generated_at"):
                            try:
                                ga = _dt.fromisoformat(
                                    str(latest["generated_at"]).replace("Z", "+00:00"),
                                )
                                if ga.tzinfo is None:
                                    ga = ga.replace(tzinfo=_tz.utc)
                                age_h = (_dt.now(_tz.utc) - ga).total_seconds() / 3600
                                if age_h <= 24:
                                    should_fire = False
                                    logger.info(
                                        f"[REGISTRY] Skip boot brief — last fired {age_h:.1f}h ago",
                                    )
                            except Exception:
                                pass
                        if should_fire:
                            # Delay 4 min so startup LLM storms settle
                            await _aio4.sleep(240)
                            logger.info("[REGISTRY] Firing boot-time Morning Brief catch-up")
                            await run_morning_brief()
                    except Exception as _be:
                        logger.warning(f"[REGISTRY] Boot brief catch-up failed: {_be}")
                _aio4.get_event_loop().create_task(_boot_catchup_brief())
            except Exception as _mbe:
                logger.warning(f"[REGISTRY] Morning Brief scheduler failed: {_mbe}")
        except Exception as ce:
            logger.warning(f"[REGISTRY] Campaign scheduler error: {ce}")

        # ── Pixel Heartbeat — every 6 hours, self-healing Phase-1 badges ──
        try:
            from services.pixel_heartbeat import run_pixel_heartbeat
            from server import db as _db

            async def _pixel_heartbeat_job():
                """Async wrapper so APScheduler awaits the coroutine.
                A bare `lambda: run_pixel_heartbeat(db)` returns a coroutine
                but APScheduler's sync executor never awaits it → leaks +
                'coroutine was never awaited' RuntimeWarning."""
                return await run_pixel_heartbeat(_db)

            aurem_scheduler.add_job(
                _pixel_heartbeat_job,
                CronTrigger(hour="2,8,14,20", minute=15, timezone="UTC"),
                id='pixel_heartbeat',
                name='Pixel Heartbeat: auto-verify AUREM pixel on all tracked sites',
                replace_existing=True,
                max_instances=1,
            )
            logger.info("[REGISTRY] Pixel Heartbeat scheduled (02:15/08:15/14:15/20:15 UTC)")
        except Exception as hb:
            logger.warning(f"[REGISTRY] Pixel Heartbeat scheduler error: {hb}")

        import asyncio as _asyncio  # local alias to avoid shadowing module-level import
        async def initial_bug_scan():
            # Delay 3 min so LLM calls at startup don't cascade OpenRouter 429 →
            # Emergent 502 → event-loop starvation. Bug Engine is not critical
            # for the first few minutes.
            await _asyncio.sleep(180)
            await scheduled_bug_scan()
        _asyncio.get_event_loop().create_task(initial_bug_scan())

        # ═══════════════════════════════════════════
        # 4-Agent Autonomous System — register + wire nightly cycle
        # ═══════════════════════════════════════════
        try:
            from services.agents import register_agents
            from services.nightly_cycle import register_nightly_jobs
            from routers.agents_router import set_db as set_agents_db
            from routers.onboarding_test_router import set_db as set_onboarding_test_db
            from utils.casl_patch import install_casl_patches
            install_casl_patches()     # CASL footer on every Resend.Emails.send
            register_agents(db)
            set_agents_db(db)
            set_onboarding_test_db(db)
            register_nightly_jobs(aurem_scheduler, db)
            # Start Follow-up ORA event listener (reacts to new_leads_batch)
            try:
                from services.agents.followup_listener import start_followup_listener
                start_followup_listener()
                logger.info("[REGISTRY] Follow-up ORA listener started")
            except Exception as le:
                logger.warning(f"[REGISTRY] Follow-up listener start failed: {le}")
            logger.info("[REGISTRY] 4-Agent system online + nightly cycle + CASL patch + onboarding test active")
        except Exception as ae:
            logger.warning(f"[REGISTRY] Agent system init failed: {ae}")

        aurem_scheduler.start()
        # iter D-63 — expose scheduler so the shutdown handler in server.py
        # can drain in-flight jobs (wait=True) on SIGTERM. Without this,
        # rolling deploys can kill jobs mid-cycle → duplicate auto-blasts,
        # half-applied stem-fixes, etc. Zero-downtime requires graceful drain.
        try:
            app.state.scheduler = aurem_scheduler
            logger.info("[REGISTRY] scheduler exposed on app.state for graceful shutdown")
        except Exception as _se:
            logger.warning(f"[REGISTRY] could not attach scheduler to app.state: {_se}")
        logger.info("[REGISTRY] AUREM Bug Engine scheduler started (every 10 min)")

        # iter D-53 — weekly self-review for CTO learning system.
        # Runs every Sunday 02:00 UTC. Aggregates the prior 7 days of
        # verified outcomes, writes a row to `cto_weekly_reports`.
        try:
            from services.cto_learning import (
                set_db as _set_learn_db,
                weekly_self_review as _weekly_review,
            )
            _set_learn_db(db)
            aurem_scheduler.add_job(
                _weekly_review,
                CronTrigger(day_of_week="sun", hour=2, minute=0,
                             timezone="UTC"),
                id="cto_learning_weekly_review",
                name="CTO Learning: weekly self-review",
                replace_existing=True,
            )
            logger.info("[REGISTRY] cto_learning weekly review scheduled "
                         "(Sun 02:00 UTC)")
        except Exception as _le:
            logger.warning(f"[REGISTRY] cto_learning weekly job not scheduled: {_le}")

        # iter D-58 — Daily Brief, Template Performance Rotation,
        # Proactive ORA sweep. Times are scoped to America/Toronto so
        # the founder sees them at their wall-clock 09:00 / 21:00 EST/EDT.
        try:
            from services.daily_brief import (
                set_db as _set_db_brief,
                send_morning_brief, send_evening_brief,
            )
            from services.template_performance import (
                set_db as _set_db_tp, weekly_rotate as _tp_rotate,
            )
            from services.proactive_ora import (
                set_db as _set_db_pa, run_all as _pa_run,
            )
            _set_db_brief(db); _set_db_tp(db); _set_db_pa(db)

            aurem_scheduler.add_job(
                send_morning_brief,
                CronTrigger(hour=9, minute=0, timezone="America/Toronto"),
                id="daily_brief_morning",
                name="Daily Brief: morning",
                replace_existing=True,
            )
            aurem_scheduler.add_job(
                send_evening_brief,
                CronTrigger(hour=21, minute=0, timezone="America/Toronto"),
                id="daily_brief_evening",
                name="Daily Brief: evening",
                replace_existing=True,
            )
            aurem_scheduler.add_job(
                _tp_rotate,
                CronTrigger(day_of_week="sun", hour=3, minute=0,
                             timezone="UTC"),
                id="template_perf_weekly_rotate",
                name="Template Performance: weekly rotation",
                replace_existing=True,
            )
            aurem_scheduler.add_job(
                _pa_run,
                CronTrigger(minute="*/30", timezone="UTC"),
                id="proactive_ora_sweep",
                name="Proactive ORA: 30-min sweep",
                replace_existing=True,
            )
            logger.info("[REGISTRY] D-58 schedulers wired "
                         "(brief 9/21 ET, perf Sun 03 UTC, proactive 30m)")
        except Exception as _d58e:
            logger.warning(f"[REGISTRY] D-58 schedulers not wired: {_d58e}")

        # iter 326pp — silent-failure alerts: any scheduled job that
        # raises now fires a single Telegram ping (dedup 5 min per
        # job_id+exception). Previously a job could crash quietly and
        # the only trace was in backend.err.log. Listener swallows all
        # errors so a bad alert never kills the scheduler itself.
        try:
            from apscheduler.events import EVENT_JOB_ERROR
            from services.silent_failure_alerts import alert_scheduler_crash

            def _on_job_error(event):
                try:
                    job = aurem_scheduler.get_job(event.job_id)
                    name = job.name if job else event.job_id
                    tb = event.traceback if hasattr(event, "traceback") else None
                    alert_scheduler_crash(
                        job_id=event.job_id,
                        job_name=name,
                        exception=event.exception,
                        tb_str=tb,
                    )
                except Exception as _le:
                    logger.warning(f"[REGISTRY] scheduler error-listener failed: {_le}")

            aurem_scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
            logger.info("[REGISTRY] Scheduler crash-alert listener attached")
        except Exception as _le:
            logger.warning(f"[REGISTRY] Could not attach scheduler error listener: {_le}")

        # iter 322 — Sentinel A2A → Council → ORA repair loop. Picks up
        # NEW client_errors every 60s, auto-heals known patterns, and
        # autonomously diagnoses the top N unique AI-eligible signatures
        # (e.g. real backend_5xx) via Claude — token-budgeted.
        try:
            from services.sentinel_repair_loop import run_sentinel_repair_cycle
            from apscheduler.triggers.interval import IntervalTrigger as _IT
            aurem_scheduler.add_job(
                run_sentinel_repair_cycle,
                _IT(seconds=300, jitter=60),
                id="sentinel_repair_loop",
                name="Sentinel Repair Loop (A2A → Council → ORA + AI Diagnose)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info("[REGISTRY] Sentinel repair loop scheduled (every 300s — was 60s, reduced to prevent event-loop pile-up)")
        except Exception as sr_e:
            logger.warning(f"[REGISTRY] Sentinel repair loop schedule failed: {sr_e}")

        # iter 325f Phase 2 — ORA CTO Repair Agent. Polls pending_approvals
        # every 5 minutes, asks the ORA CTO daemon for a proposed fix, and
        # routes tier-1 fixes to auto-apply (with the 5-min cancel window
        # baked into the row) or tier-2 to a Telegram founder approval.
        try:
            from services.ora_cto_repair_agent import (
                run_repair_tick as _cto_repair_tick,
            )
            from apscheduler.triggers.interval import IntervalTrigger as _IT2
            aurem_scheduler.add_job(
                _cto_repair_tick,
                _IT2(seconds=300, jitter=30),
                id="ora_cto_repair_agent",
                name="ORA CTO Repair Agent (pending_approvals → CTO → tier-1/2)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info("[REGISTRY] ORA CTO repair agent scheduled (every 300s)")
        except Exception as cto_e:
            logger.warning(f"[REGISTRY] ORA CTO repair agent schedule failed: {cto_e}")

        # iter 325f Phase 3a — Self-Audit auto-trigger (every 6h). Findings
        # with severity HIGH flow to incident_bus so the rest of the stack
        # can react. Previously manual-only.
        try:
            from services.self_audit_scheduler import run_self_audit_tick
            from apscheduler.triggers.interval import IntervalTrigger as _IT3
            aurem_scheduler.add_job(
                run_self_audit_tick,
                _IT3(hours=6, jitter=300),
                id="self_audit_cron",
                name="Self-Audit (6h auto-run → incident_bus on HIGH)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            logger.info("[REGISTRY] Self-audit cron scheduled (every 6h)")
        except Exception as sa_e:
            logger.warning(f"[REGISTRY] Self-audit cron failed: {sa_e}")

        # iter 325f Phase 4 — Shannon Autofix scheduler. Runs after every
        # Shannon scan (poll-based: every 30 min). HIGH/CRITICAL findings
        # already flow via shannon_security.ingest_report → pending_approvals.
        # This scheduler covers LOW/MEDIUM gaps by asking ORA CTO for fix
        # suggestions on un-proposed findings.
        try:
            from services.shannon_autofix import shannon_autofix_tick
            from apscheduler.triggers.interval import IntervalTrigger as _IT4
            aurem_scheduler.add_job(
                shannon_autofix_tick,
                _IT4(minutes=30, jitter=120),
                id="shannon_autofix",
                name="Shannon Autofix (LOW/MED findings → ORA CTO proposals)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info("[REGISTRY] Shannon autofix scheduled (every 30 min)")
        except Exception as sx_e:
            logger.warning(f"[REGISTRY] Shannon autofix schedule failed: {sx_e}")

        # iter 325f Phase 5 — React Doctor weekly monitor. Reads the
        # latest react_doctor_runs row, compares against previous; >5-pt
        # drop emits incident_bus, <50 absolute fires Telegram.
        try:
            from services.react_doctor_monitor import react_doctor_monitor_tick
            from apscheduler.triggers.interval import IntervalTrigger as _IT5
            aurem_scheduler.add_job(
                react_doctor_monitor_tick,
                _IT5(days=7, jitter=3600),
                id="react_doctor_monitor",
                name="React Doctor Monitor (weekly, score drop → incident_bus)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            logger.info("[REGISTRY] React Doctor monitor scheduled (weekly)")
        except Exception as rd_e:
            logger.warning(f"[REGISTRY] React Doctor monitor failed: {rd_e}")

        # iter D-73a — Twilio breaker auto-probe.
        # When the breaker is OPEN (creds returned 401), probe Twilio
        # every 5 min and AUTO-RECOVER on 200. No more manual restart
        # after rotating TWILIO_AUTH_TOKEN. Cheap no-op when closed.
        try:
            from services.twilio_auth_breaker import auto_probe_tick, PROBE_INTERVAL_S
            aurem_scheduler.add_job(
                auto_probe_tick,
                trigger="interval",
                seconds=PROBE_INTERVAL_S,
                id="twilio_auth_auto_probe",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info(f"[REGISTRY] Twilio auth auto-probe scheduled (every {PROBE_INTERVAL_S}s, open-only)")
        except Exception as tap_e:
            logger.warning(f"[REGISTRY] Twilio auth auto-probe failed: {tap_e}")

        # iter 324l — Scout Replenish Cron. Keeps campaign_leads queue topped
        # up via OSM hunts every 2h so auto_blast_engine never starves.
        try:
            from services.scout_replenish_cron import (
                install_scheduler as _install_scout_cron,
                set_db as _set_scout_cron_db,
            )
            _set_scout_cron_db(db)
            _install_scout_cron(aurem_scheduler)
        except Exception as sc_e:
            logger.warning(f"[REGISTRY] Scout replenish cron schedule failed: {sc_e}")

        # iter 324p — Warm Prober. Pings /api/health every 90s so cold-start
        # never hits a real customer. K8s pod warm-up latency was 15-25s
        # on first hit before this — see iter 324o E2E audit.
        try:
            from services.warm_prober import install_scheduler as _install_warm_prober
            _install_warm_prober(aurem_scheduler)
        except Exception as wp_e:
            logger.warning(f"[REGISTRY] Warm prober schedule failed: {wp_e}")

        # iter 326w — Tier 2 Auto-Executor. Every 5 s, atomically claims
        # any tier2 pending action whose 30-second cancel window has
        # elapsed and runs the standard approve path. Tier 3 actions
        # are NEVER touched — those still need an explicit founder click.
        #
        # iter 332b D-25 — production memory mitigation. On the prod K8s
        # pod this loop fires every 5s, and when DB reads are slow the
        # next tick overlaps and APScheduler logs "max instances reached"
        # every cycle. Bumping prod to 30s eliminates the overlap warning
        # AND drops the cron load by 6×. The 30s cancel window is the
        # natural floor — running faster than that buys nothing.
        try:
            # iter 332b D-26 — inline production detection (the module-level
            # helper wasn't visible inside this nested registration block on
            # the hot-reloaded runtime, throwing NameError). Inlining is
            # cheap and dependency-free.
            _h = (os.environ.get("HOSTNAME") or "").lower()
            _is_prod = (
                ("live-support" in _h or "emergent.host" in _h)
                or (os.environ.get("KUBERNETES_SERVICE_HOST")
                    and not _h.startswith("agent-env-")
                    and not _h.startswith("preview-")
                    and not os.environ.get("preview_endpoint"))
            )
            if os.environ.get("AUREM_FORCE_FULL_MODE", "").strip() in ("1", "true", "yes"):
                _is_prod = False
            _t2_interval = 30 if _is_prod else 5
            from services.ora_agent import auto_execute_due_tier2
            from apscheduler.triggers.interval import IntervalTrigger as _IT_T2
            async def _tier2_auto_exec_tick():
                try:
                    await auto_execute_due_tier2()
                except Exception as _e:
                    logger.debug(f"[tier2-auto-exec] tick error: {_e}")
            aurem_scheduler.add_job(
                _tier2_auto_exec_tick,
                _IT_T2(seconds=_t2_interval),
                id="tier2_auto_executor",
                name="ORA Tier 2 Auto-Executor (30s cancel window)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info(f"[REGISTRY] tier2 auto-executor scheduled (every {_t2_interval}s)")
        except Exception as t2_e:
            logger.warning(f"[REGISTRY] tier2 auto-executor schedule failed: {t2_e}")

        # iter 323g — Pixel → ORA Bridge (5 min cron, no LLM call inside)
        try:
            from services.pixel_to_ora_bridge import PixelToOraBridge
            from apscheduler.triggers.interval import IntervalTrigger as _IT_PB
            _pb = PixelToOraBridge()
            async def _pixel_bridge_job():
                await _pb.run_cycle(db)
            aurem_scheduler.add_job(
                _pixel_bridge_job,
                _IT_PB(seconds=300, jitter=30),
                id="pixel_to_ora_bridge",
                name="Pixel → ORA Bridge (5 min scan, enqueue only)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=120,
            )
            logger.info("[REGISTRY] Pixel → ORA Bridge scheduled (every 300s)")
        except Exception as pb_e:
            logger.warning(f"[REGISTRY] Pixel→ORA bridge schedule failed: {pb_e}")

        # iter 322 — Trial reminder + expiry sweep (hourly)
        try:
            from services.trial_reminder_scheduler import trial_reminder_tick
            from apscheduler.triggers.interval import IntervalTrigger as _IT2
            aurem_scheduler.add_job(
                trial_reminder_tick,
                _IT2(hours=1),
                id="trial_reminder_tick",
                name="Trial Reminder + Expiry Sweep",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] Trial reminder scheduler attached (hourly)")
        except Exception as tr_e:
            logger.warning(f"[REGISTRY] Trial reminder schedule failed: {tr_e}")

        # iter 322 — Daily usage snapshot (3am UTC)
        try:
            from services.usage_reset_scheduler import usage_reset_tick
            from apscheduler.triggers.cron import CronTrigger as _CT
            aurem_scheduler.add_job(
                usage_reset_tick,
                _CT(hour=3, minute=0),
                id="usage_reset_tick",
                name="Daily Usage Snapshot",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] Usage snapshot scheduler attached (daily 03:00 UTC)")
        except Exception as ur_e:
            logger.warning(f"[REGISTRY] Usage snapshot schedule failed: {ur_e}")

        # iter 322 — Autonomous ORA proposal bridge (every 60s).
        # Drains repair_suggestions + migration signals + persistent_red into
        # the existing ORA Dev Console queue, so founder one-click approves
        # instead of running curl/console blocks manually.
        try:
            from services.ora_proposal_bridge import ora_bridge_tick
            from apscheduler.triggers.interval import IntervalTrigger as _IT3
            aurem_scheduler.add_job(
                ora_bridge_tick,
                _IT3(seconds=300, jitter=60),
                id="ora_proposal_bridge",
                name="Autonomous ORA Proposal Bridge (sentinel/health → Dev Console)",
                replace_existing=True,
                # iter 326e — bump from max_instances=1, prod logs were
                # spamming "maximum number of running instances reached (1)"
                # because tick latency can spike on cold-start DeepSeek calls.
                max_instances=2,
                coalesce=True,
                misfire_grace_time=180,
            )
            logger.info("[REGISTRY] ORA proposal bridge scheduled (every 300s — was 60s)")
        except Exception as ob_e:
            logger.warning(f"[REGISTRY] ORA proposal bridge schedule failed: {ob_e}")

        # iter 322u — Watchdog for the bridge itself (every 5 min).
        # Re-arms the job if its heartbeat is stale; logs to truth_ledger
        # and pushes a founder_notification.
        try:
            from services.ora_proposal_bridge import ora_bridge_watchdog
            from apscheduler.triggers.interval import IntervalTrigger as _IT4
            aurem_scheduler.add_job(
                ora_bridge_watchdog,
                _IT4(seconds=300),
                id="ora_proposal_bridge_watchdog",
                name="ORA Bridge Watchdog (5min stale-heartbeat re-arm)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] ORA proposal bridge watchdog scheduled (every 5min)")
        except Exception as wd_e:
            logger.warning(f"[REGISTRY] ORA proposal bridge watchdog schedule failed: {wd_e}")

        # iter 322v — Daily agent skill snapshot (00:00 UTC)
        try:
            from routers.training_dashboard_router import snapshot_agent_skills_daily
            from apscheduler.triggers.cron import CronTrigger as _CT_skills
            aurem_scheduler.add_job(
                snapshot_agent_skills_daily,
                _CT_skills(hour=0, minute=0),
                id="agent_skills_daily_snapshot",
                name="Daily Agent Skill Snapshot (30d rolling)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] Daily agent skills snapshot scheduled (00:00 UTC)")
        except Exception as as_e:
            logger.warning(f"[REGISTRY] agent skills snapshot schedule failed: {as_e}")

        # iter 322w STEP 2 — Hourly trial-expiry sweep
        try:
            from services.trial_expiry_sweep import trial_expiry_sweep
            from apscheduler.triggers.interval import IntervalTrigger as _IT_trial
            aurem_scheduler.add_job(
                trial_expiry_sweep,
                _IT_trial(hours=1),
                id="trial_expiry_sweep",
                name="Trial Expiry Sweep (every 1h — locks expired trials + sends email)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] Trial expiry sweep scheduled (every 1h)")
        except Exception as te_e:
            logger.warning(f"[REGISTRY] trial expiry sweep schedule failed: {te_e}")

        # iter 322ar — Collective Scan (25 agents, every 1 hour)
        try:
            from services import collective_scanner as _cs_mod
            _cs_mod.set_db(db)
            from apscheduler.triggers.interval import IntervalTrigger as _IT_cs
            aurem_scheduler.add_job(
                _cs_mod.run_cycle,
                _IT_cs(hours=1),
                id="collective_scan",
                name="Collective Scan (25 agents, peer-review v2)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            logger.info("[REGISTRY] Collective Scan scheduled (every 1h)")
        except Exception as cs_e:
            logger.warning(f"[REGISTRY] collective scan schedule failed: {cs_e}")

        # iter 281.5 — Phase 2.5 retention + upsell schedulers
        try:
            from services.ora_phase_25 import attach_phase_25_scheduler
            if attach_phase_25_scheduler(aurem_scheduler, db):
                logger.info("[REGISTRY] ORA Phase 2.5 retention+upsell schedulers attached")
        except Exception as p25_e:
            logger.warning(f"[REGISTRY] Phase 2.5 scheduler attach failed: {p25_e}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[REGISTRY] AUREM scheduler error: {e}")

    # Diagnostic endpoint
    try:
        from routers.diagnostic_router import router as diagnostic_router, set_db as set_diagnostic_db
        set_diagnostic_db(db)
        app.include_router(diagnostic_router)
    except Exception as e:
        logger.warning(f"Diagnostic router not loaded: {e}")

    # ORA Avatar router (Phase 1/2/8 — customer prefs + admin manager)
    try:
        from routers.ora_avatar_router import (
            router as ora_avatar_router,
            _admin_router as ora_avatar_admin_router,
            set_db as set_ora_avatar_db,
        )
        set_ora_avatar_db(db)
        app.include_router(ora_avatar_router, prefix="/api")
        app.include_router(ora_avatar_admin_router, prefix="/api")
    except Exception as e:
        logger.warning(f"ORA Avatar router not loaded: {e}")

    # iter 322ar — Collective Scan router (POST /run, GET /last/recent/dependency-map)
    try:
        from routers.collective_scan_router import (
            router as collective_scan_router,
            set_db as set_collective_db,
        )
        set_collective_db(db)
        app.include_router(collective_scan_router)
        logger.info("[REGISTRY] Collective Scan router registered")
    except Exception as e:
        logger.warning(f"Collective Scan router not loaded: {e}")

    # iter 322ar — ORA Universal Learner wiring (used by hooks across
    # scout/hunter/council/sentinel/website-builder/auth/intel/bin-ora).
    try:
        from services import ora_universal_learner as _oul
        _oul.set_db(db)
        logger.info("[REGISTRY] ORA universal learner wired")
    except Exception as e:
        logger.warning(f"ORA universal learner not wired: {e}")

    # iter 322ar — White-Label admin router (branding/cname endpoints)
    try:
        from routers.white_label_router import (
            router as wl_router,
            set_db as set_wl_db,
        )
        set_wl_db(db)
        app.include_router(wl_router)
        logger.info("[REGISTRY] White-Label router registered")
    except Exception as e:
        logger.warning(f"White-Label router not loaded: {e}")

    # iter 322as — Public booking router (used by embedded widget.js)
    try:
        from routers.public_booking_router import (
            router as pub_book_router,
            set_db as set_pub_book_db,
        )
        set_pub_book_db(db)
        app.include_router(pub_book_router)
        logger.info("[REGISTRY] Public booking router registered")
    except Exception as e:
        logger.warning(f"Public booking router not loaded: {e}")

    # iter 322au — Build Journal router (Day-1 build data → ORA Learning Stack)
    try:
        from routers.build_journal_router import (
            public_router as bj_public,
            admin_router as bj_admin,
            set_db as set_bj_db,
        )
        set_bj_db(db)
        app.include_router(bj_public)
        app.include_router(bj_admin)
        logger.info("[REGISTRY] Build Journal router registered")

        # ── Auto-backfill on first boot (idempotent, runs once per startup) ──
        try:
            import asyncio as _aio
            from services import build_journal_service as _bj_svc

            async def _build_journal_first_boot():
                try:
                    res = await _bj_svc.backfill(db, limit=5000)
                    logger.info(f"[REGISTRY] Build Journal backfill: {res}")
                except Exception as bex:
                    logger.warning(f"[REGISTRY] Build Journal backfill failed: {bex}")

            _aio.get_event_loop().create_task(_build_journal_first_boot())
        except Exception as e:
            logger.warning(f"[REGISTRY] Build Journal first-boot task: {e}")

        # ── Phase 2 — Live sync every 10 min ─────────────────────────────
        try:
            from apscheduler.triggers.interval import IntervalTrigger
            from apscheduler.triggers.cron import CronTrigger

            async def _bj_live_sync_job():
                try:
                    from services import build_journal_service as _bj
                    await _bj.live_sync(db)
                except Exception as e:
                    logger.warning(f"[bj-sync] {e}")

            aurem_scheduler.add_job(
                _bj_live_sync_job,
                IntervalTrigger(minutes=10),
                id="build_journal_live_sync",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            # ── Phase 4 — Daily founder digest 04:00 UTC (≈23:00 Toronto) ──
            async def _bj_digest_job():
                try:
                    from services import build_journal_service as _bj
                    res = await _bj.send_daily_digest(db)
                    logger.info(f"[bj-digest] {res}")
                except Exception as e:
                    logger.warning(f"[bj-digest] {e}")

            aurem_scheduler.add_job(
                _bj_digest_job,
                CronTrigger(hour=4, minute=0),
                id="build_journal_daily_digest",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            # ── Phase 5 — ORA Pattern Miner 03:30 UTC ────────────────────
            async def _bj_miner_job():
                try:
                    from services import build_journal_service as _bj
                    res = await _bj.mine_patterns(db)
                    logger.info(f"[bj-miner] {res}")
                except Exception as e:
                    logger.warning(f"[bj-miner] {e}")

            aurem_scheduler.add_job(
                _bj_miner_job,
                CronTrigger(hour=3, minute=30),
                id="build_journal_pattern_miner",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )

            logger.info("[REGISTRY] Build Journal schedulers wired — live-sync 10m, digest 04:00, miner 03:30")
        except Exception as e:
            logger.warning(f"[REGISTRY] Build Journal scheduler wiring failed: {e}")

    except Exception as e:
        logger.warning(f"Build Journal router not loaded: {e}")

    # iter 322av — Nightly Self-Check (runs every morning + night, autoheals)
    try:
        from routers.nightly_selfcheck_router import (
            router as nsc_router, set_db as set_nsc_db,
        )
        set_nsc_db(db)
        app.include_router(nsc_router)
        from apscheduler.triggers.cron import CronTrigger as _SCCron
        from apscheduler.triggers.interval import IntervalTrigger as _SCInterval

        async def _selfcheck_morning():
            from services.aurem_nightly_selfcheck import run_selfcheck
            await run_selfcheck(db, slot="morning")

        async def _selfcheck_nightly():
            from services.aurem_nightly_selfcheck import run_selfcheck
            await run_selfcheck(db, slot="nightly")

        aurem_scheduler.add_job(_selfcheck_morning, _SCCron(hour=6, minute=30),
                                id="aurem_selfcheck_morning", replace_existing=True,
                                max_instances=1, coalesce=True)
        aurem_scheduler.add_job(_selfcheck_nightly, _SCCron(hour=21, minute=30),
                                id="aurem_selfcheck_nightly", replace_existing=True,
                                max_instances=1, coalesce=True)
        logger.info("[REGISTRY] Nightly self-check wired — morning 06:30 UTC, nightly 21:30 UTC")

        # iter 326vv — Morning brief scheduler. The helper
        # `services.morning_brief.morning_brief_scheduler` was defined
        # but never started, so briefs were generated by ad-hoc internal
        # callers and never delivered (founder_brief_sends had 0 rows).
        # Wire to APScheduler so it runs daily at 07:00 America/Toronto
        # and goes through the real deliver_brief() pipeline (WhatsApp +
        # email + push) with audit logged in founder_brief_sends.
        async def _morning_brief_job():
            try:
                from services.morning_brief import run_morning_brief
                res = await run_morning_brief()
                logger.info(
                    f"[morning-brief] cron run — brief_id={res.get('brief_id')} "
                    f"delivered={res.get('delivered')} channels={res.get('sent_channels')}"
                )
            except Exception as e:
                logger.exception(f"[morning-brief] cron failed: {e}")
        try:
            aurem_scheduler.add_job(
                _morning_brief_job,
                _SCCron(hour=7, minute=0, timezone="America/Toronto"),
                id="aurem_morning_brief_daily",
                name="AUREM Morning Brief (07:00 ET)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=900,
            )
            logger.info("[REGISTRY] Morning brief cron scheduled — daily 07:00 America/Toronto")
        except Exception as _e:
            logger.warning(f"[REGISTRY] Morning brief cron failed to register: {_e}")

        # ── iter 322av — ORA Autonomous Driver (fully self-driving) ──
        async def _daily_hunt_job():
            from services.ora_autonomous_driver import daily_hunt_for_all_tenants
            try:
                res = await daily_hunt_for_all_tenants(db)
                logger.info(f"[ora-driver] daily hunt — {res.get('leads_sourced')} leads across {res.get('tenants_scanned')} tenants")
            except Exception as e:
                logger.warning(f"[ora-driver] daily hunt failed: {e}")

        async def _watchdog_job():
            from services.ora_autonomous_driver import ora_watchdog
            try:
                await ora_watchdog(db)
            except Exception as e:
                logger.warning(f"[ora-driver] watchdog tick failed: {e}")

        # Daily hunt — 06:00 UTC = 02:00 Toronto
        aurem_scheduler.add_job(_daily_hunt_job, _SCCron(hour=6, minute=0),
                                id="ora_daily_hunt", replace_existing=True,
                                max_instances=1, coalesce=True)
        # Watchdog — every 15 min, 24/7
        aurem_scheduler.add_job(_watchdog_job, _SCInterval(minutes=15),
                                id="ora_watchdog", replace_existing=True,
                                max_instances=1, coalesce=True)
        logger.info("[REGISTRY] ORA Autonomous Driver wired — daily hunt 06:00 UTC, watchdog every 15min")

        # iter 327m — Stripe metered-billing cron. Until this iter,
        # BillingService.record_overage() existed and was tested but
        # NO production code path actually invoked it — i.e. customer
        # overages tracked in business_workspace_usage were NEVER
        # reported to Stripe and the founder lost revenue every
        # billing cycle. This job walks every workspace at 03:00 UTC
        # daily; for any workspace whose `current_period_end` has
        # passed AND has unreported overage messages, it posts a
        # Stripe MeterEvent via record_overage and stamps an audit row.
        async def _billing_overage_job():
            try:
                from shared.commercial.billing_service import BillingService
                from datetime import datetime, timezone
                bs = BillingService(db)
                now = datetime.now(timezone.utc)
                reported = 0
                cur = db.workspaces.find(
                    {
                        # Workspaces that have a billing block with a meter
                        # event and a period end in the past — i.e. we're
                        # post-period and haven't reported yet.
                        "billing.stripe_meter_event_name": {"$exists": True},
                        "billing.current_period_end":      {"$lte": now.isoformat()},
                    },
                    {"_id": 0, "business_id": 1, "billing": 1},
                ).limit(200)
                async for ws in cur:
                    bid = ws.get("business_id")
                    if not bid:
                        continue
                    try:
                        await bs.record_overage(business_id=bid)
                        reported += 1
                    except Exception as inner:
                        logger.warning(
                            f"[billing-cron] record_overage failed for "
                            f"{bid}: {type(inner).__name__}: {str(inner)[:120]}"
                        )
                logger.info(f"[billing-cron] daily overage sweep — reported={reported}")
            except Exception as e:
                logger.warning(f"[billing-cron] daily overage job failed: {e}")

        aurem_scheduler.add_job(
            _billing_overage_job,
            _SCCron(hour=3, minute=0),
            id="aurem_stripe_overage_daily",
            name="Stripe metered overage sweep (03:00 UTC)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )
        logger.info("[REGISTRY] Stripe overage cron scheduled — daily 03:00 UTC")

        # iter 327q — ORA auto-resume tick (FIX 1 + FIX 5).
        # Every 30 seconds, drain pending rows from ora_auto_resume_queue
        # so long-running ORA tasks that hit ORA_MAX_LOOP_S transparently
        # continue without the founder typing "continue".
        async def _ora_auto_resume_job():
            try:
                from services.ora_agent import auto_resume_tick
                out = await auto_resume_tick()
                if out.get("drained") or out.get("failed"):
                    logger.info(
                        f"[ora-auto-resume] drained={out.get('drained')} "
                        f"failed={out.get('failed')}"
                    )
            except Exception as e:
                logger.warning(f"[ora-auto-resume] tick failed: {e}")

        aurem_scheduler.add_job(
            _ora_auto_resume_job,
            "interval",
            seconds=30,
            id="aurem_ora_auto_resume",
            name="ORA auto-resume tick (every 30s)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        logger.info("[REGISTRY] ORA auto-resume tick scheduled — every 30s")

        # iter 327q — ORA nightly self-test (FIX 2).
        # Runs 5 standard checks at 02:00 UTC; on any failure fires a
        # Telegram alert BEFORE the morning brief so the founder wakes
        # up to a clear single-line report.
        async def _ora_nightly_self_test_job():
            try:
                from services.ora_nightly_self_test import run_nightly_self_test
                await run_nightly_self_test(db)
            except Exception as e:
                logger.warning(f"[ora-nightly-self-test] failed: {e}")

        aurem_scheduler.add_job(
            _ora_nightly_self_test_job,
            _SCCron(hour=2, minute=0),
            id="aurem_ora_nightly_self_test",
            name="ORA nightly self-test (02:00 UTC)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=1800,
        )
        logger.info("[REGISTRY] ORA nightly self-test scheduled — daily 02:00 UTC")

        # iter 328b — PIPEDA daily retention sweep (04:00 UTC).
        async def _pipeda_sweep_job():
            try:
                from services.data_retention import run_retention_sweep
                out = await run_retention_sweep(db)
                logger.info(f"[pipeda-cron] {out}")
            except Exception as e:
                logger.warning(f"[pipeda-cron] failed: {e}")

        aurem_scheduler.add_job(
            _pipeda_sweep_job,
            _SCCron(hour=4, minute=0),
            id="aurem_pipeda_daily_sweep",
            name="PIPEDA retention sweep (04:00 UTC)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        logger.info("[REGISTRY] PIPEDA retention cron scheduled — daily 04:00 UTC")

        # iter 328f — SLA snapshot every 15 min. Cheap (4 small queries)
        # and fires Telegram alerts only on transition to breach.
        async def _sla_snapshot_job():
            try:
                from services.sla_metrics import (
                    compute_sla_snapshot, maybe_alert_sla_breach,
                )
                snap = await compute_sla_snapshot(db)
                await maybe_alert_sla_breach(db, snap)
            except Exception as e:
                logger.warning(f"[sla-cron] failed: {e}")

        aurem_scheduler.add_job(
            _sla_snapshot_job,
            "interval",
            minutes=15,
            id="aurem_sla_snapshot",
            name="SLA snapshot + alert (every 15 min)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        logger.info("[REGISTRY] SLA snapshot cron scheduled — every 15 min")

        # iter 328c — External uptime monitor staleness check.
        # If the external service (UptimeRobot) stops pinging us, we
        # fire a Telegram alert once per hour. Cheap — single Mongo
        # lookup per tick.
        async def _external_uptime_check_job():
            try:
                from services.external_uptime_monitor import staleness_check
                await staleness_check(db)
            except Exception as e:
                logger.warning(f"[ext-uptime-cron] failed: {e}")

        aurem_scheduler.add_job(
            _external_uptime_check_job,
            "interval",
            minutes=10,
            id="aurem_external_uptime_check",
            name="External uptime staleness check (every 10 min)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
        logger.info("[REGISTRY] External uptime staleness cron scheduled — every 10 min")

        # iter 330 FIX 1 — Closer Day-5 trigger every 30 min.
        async def _closer_day5_job():
            try:
                from services.closer_day5_trigger import run_closer_day5_sweep
                out = await run_closer_day5_sweep(db)
                if out.get("armed") or out.get("errors"):
                    logger.info(f"[closer-day5] {out}")
            except Exception as e:
                logger.warning(f"[closer-day5] failed: {e}")

        aurem_scheduler.add_job(
            _closer_day5_job,
            "interval",
            minutes=30,
            id="aurem_closer_day5",
            name="Retell Day-5 trigger (every 30 min)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
        logger.info("[REGISTRY] Retell Day-5 trigger scheduled — every 30 min")

        # iter 330 FIX 3 — Reply-inbox → ORA bridge every 5 min.
        async def _reply_inbox_job():
            try:
                from services.reply_inbox_processor import reply_inbox_sweep
                out = await reply_inbox_sweep(db)
                if out.get("processed"):
                    logger.info(f"[reply-inbox] {out}")
            except Exception as e:
                logger.warning(f"[reply-inbox] failed: {e}")

        aurem_scheduler.add_job(
            _reply_inbox_job,
            "interval",
            minutes=5,
            id="aurem_reply_inbox",
            name="Reply-inbox → ORA bridge (every 5 min)",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=120,
        )
        logger.info("[REGISTRY] Reply-inbox bridge scheduled — every 5 min")

        # iter 330 FIX 6 — Social autopilot daily 10:00 America/Toronto.
        async def _social_autopilot_job():
            try:
                from services.social_autopilot import run_daily_social_post
                out = await run_daily_social_post(db)
                logger.info(f"[social-autopilot] {out}")
            except Exception as e:
                logger.warning(f"[social-autopilot] failed: {e}")

        try:
            import pytz
            tor_tz = pytz.timezone("America/Toronto")
            aurem_scheduler.add_job(
                _social_autopilot_job,
                _SCCron(hour=10, minute=0, timezone=tor_tz),
                id="aurem_social_autopilot",
                name="LinkedIn autopilot (10:00 America/Toronto)",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            logger.info("[REGISTRY] Social autopilot scheduled — daily 10:00 ET")
        except Exception as e:
            logger.warning(f"[REGISTRY] Social autopilot schedule failed: {e}")

        # iter 330 FIX 2 — Founder-facing alert: surface missing Twilio
        # WABA config on startup so WhatsApp isn't a silent hole. Sent
        # once per day (fingerprint by date) so the founder isn't
        # spammed across pod restarts.
        try:
            import os as _os
            from datetime import datetime as _dt
            tw_set = bool((_os.environ.get("TWILIO_WA_FROM_NUMBER") or "").strip())
            whapi_disabled = (_os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
                              in ("1", "true", "yes", "on"))
            if not tw_set and whapi_disabled:
                async def _wa_gap_alert():
                    try:
                        from services.silent_failure_alerts import _send as _tg
                        day = _dt.utcnow().strftime("%Y-%m-%d")
                        await _tg(
                            "📵 WhatsApp outreach OFF — TWILIO_WA_FROM_NUMBER is empty "
                            "and WHAPI_BLAST_DISABLED=true. Set TWILIO_WA_FROM_NUMBER "
                            "(format: 'whatsapp:+14155238886') + TWILIO_WA_TEMPLATE_SID "
                            "to unlock the cheapest CASL-compliant channel.",
                            fingerprint=f"wa_outreach_gap_{day}",
                        )
                    except Exception:
                        pass
                # Fire once 60 s after boot so logs settle first.
                aurem_scheduler.add_job(
                    _wa_gap_alert, "date",
                    run_date=_dt.utcnow() + timedelta(seconds=60),
                    id="aurem_wa_gap_alert_once",
                    replace_existing=True,
                )
        except Exception as e:
            logger.debug(f"[REGISTRY] WA gap alert wiring failed: {e}")

    except Exception as e:
        logger.warning(f"Nightly self-check not wired: {e}")


    # ═══════════════════════════════════════════
    # LEAN MODE: Post-registration route cleanup
    # See routers/_registry_lean_prune.py for the full prune-list.
    # ═══════════════════════════════════════════
    apply_lean_prune(app, LEAN_MODE)

    logger.info("[REGISTRY] All routers registered")
