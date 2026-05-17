"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.
All rights reserved. Unauthorized copying, distribution,
or use of this software is strictly prohibited.
Licensed under Polaris Built Inc. commercial license.

Startup Initialization — Bulk service DB init and background scheduler functions.
Extracted from server.py Phase 2 modularization.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def _safe_task(coro, name="unnamed"):
    """Wrap coroutine so unhandled exceptions never crash the process."""
    async def _wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            pass
        except BaseException as exc:
            logger.error(f"[SAFE_TASK] '{name}' crashed: {exc}")
    task = asyncio.create_task(_wrapper(), name=name)
    return task


def init_all_service_dbs(db):
    """
    Bulk-initialize all service modules with the database reference.
    Replaces ~500 lines of individual set_db() calls from server.py.
    """
    # Simple set_db modules (import path, set_db function name or 'set_db')
    _simple_modules = [
        "routers.ai_email_router",
        "routers.whatsapp_alerts",
        "routers.weather_skincare",
        "routers.biometric_auth",
        "routers.github_integration",
        "routers.toon_router",
        "routers.generative_ui_router",
        "routers.push_notification_router",
        "routers.system_pulse_router",
        "routers.tenant_migration_router",
        "routers.nexus_router",
        "routers.subscription_router",
        "routers.owner_panel_router",
        "routers.skin_analysis_router",
        "routers.sms_alerts_router",
        "routers.sentiment_analysis_router",
        "routers.product_ai_router",
        "routers.translation_router",
        "routers.inventory_ai_router",
        "routers.aurem_billing_router",
        "routers.action_engine_router",
        "routers.aurem_keys_router",
        "routers.aurem_llm_proxy_router",
        "routers.brain_router",
        "routers.unified_inbox_router",
        "routers.whatsapp_webhook_router",
        "routers.voice_router",
        "routers.voice_analytics_router",
        "routers.agent_reach_router",
        "routers.morning_brief_router",
        "routers.omnidim_router",
        "routers.churn_prediction_router",
        "routers.document_scanner_router",
        "routers.video_generation_router",
        "routers.appointment_scheduler_router",
        "routers.a2a_learning_router",
        "routers.orchestrator_brain_router",
        "routers.llm_router",
        "routers.browser_agent_router",
        "routers.voice_layer_router",
        "routers.crew_ai_router",
        "routers.ooda_loop_router",
        "routers.ai_platform_router",
        "routers.aurem_vanguard_router",
        "routers.business_routes",
        "routers.premium_routes",
        "routers.system_routes",
        "routers.digest_routes",
        "routers.leads_router",
        "routers.shopify_webhook_router",
        "routers.panic_settings_router",
        "routers.panic_takeover_router",
        "routers.vapi_voice_router",
        "routers.v2v_stream_engine",
        "routers.super_admin_analytics_router",
        "routers.voice_profile_router",
        "routers.ora_pwa_router",
        "routers.settings_router",
        "routers.crm_router",
        "routers.gateway_router",
        "routers.automations_router",
        "routers.referral_router",
        "routers.vault_router",
        "routers.acquisition_router",
        "routers.client_manager_router",
        "routers.extension_leads_router",
        "routers.revenue_engine",
        "routers.enterprise_engine",
        "routers.shopify_storefront_engine",
        "routers.onboarding_router",
        "routers.intelligence_api",
        "routers.agent_execution_router",
        "routers.training_dashboard_router",
        "routers.aurem_routes",
        "routers.aurem_chat",
        "routers.ora_dispatcher_router",
        "routers.clawchief_router",
        "routers.highsignal_router",
        "routers.critic_router",
        "routers.openrouter_router",
        "routers.password_reset_router",
        "routers.stripe_payment_router",
        "routers.google_oauth_callback",
        "routers.shopify_billing_router",
        "routers.aurem_platform_router",
        "routers.google_oauth_router",
        "routers.gmail_channel_router",
        "routers.tenant_optimization_router",
        "routers.pipeline_router",
        "routers.approval_router",
        "routers.brief_router",
        "routers.memory_router",
        "routers.security_audit_router",
        "routers.openclaw_router",
        "routers.negotiation_router",
        "routers.document_rag_router",
        "routers.lead_enrichment_router",
        "routers.deep_scout_router",
        "routers.sentinel_anomaly_router",
        "routers.revenue_forecast_router",
        "routers.honeypot_router",
        "middleware.db_audit",
        "services.plan_enforcement",
        "services.auto_heal",
        "services.memory_tiers",
        "services.auto_repair",
    ]

    count = 0
    for module_path in _simple_modules:
        try:
            mod = __import__(module_path, fromlist=["set_db"])
            if hasattr(mod, "set_db"):
                mod.set_db(db)
                count += 1
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[INIT] {module_path} set_db failed: {e}")

    # Special set_db_ref for local_llm_router
    try:
        from routers.local_llm_router import set_db_ref
        set_db_ref(db)
        count += 1
    except Exception:
        pass

    # Inline routers
    for mod_name in [
        'auth_inline', 'product_inline', 'cart_inline', 'order_inline',
        'payment_inline', 'admin_inline', 'influencer_inline',
        'store_settings_inline', 'analytics_inline', 'subscriber_inline',
        'seo_inline', 'shipping_qr_inline', 'blog_inline',
        'founding_inline', 'postal_inline',
    ]:
        try:
            mod = __import__(f'routers.{mod_name}', fromlist=['set_db'])
            if hasattr(mod, 'set_db'):
                mod.set_db(db)
                count += 1
        except Exception:
            pass

    # AUREM Security modules
    try:
        from utils.aurem_secrets import init_aurem_security
        from utils.aurem_rate_limiter import set_db as set_rate_limiter_db
        from utils.aurem_jwt import set_db as set_jwt_db
        from utils.aurem_rls import set_db as set_rls_db
        from utils.aurem_security_middleware import set_db as set_security_mw_db
        init_aurem_security(strict=False)
        set_rate_limiter_db(db)
        set_jwt_db(db)
        set_rls_db(db)
        set_security_mw_db(db)
        count += 4
    except ImportError:
        pass

    logger.info(f"[INIT] Bulk service DB init complete: {count} modules initialized")
    return count


async def init_aurem_indexes(db):
    """Initialize AUREM commercial platform indexes in background.

    iter 322ee — Gated the truly-empty commercial scaffolding behind
    `AUREM_COMMERCIAL_FEATURES=1`. The TokenVault/ConsentTracker/Gmail/
    UnifiedInbox/WhatsApp/KeyService collections sit empty in production
    (AUREM is currently SaaS-focused, not the multi-tenant commercial
    platform these were built for). Indexes still got created on every
    restart, auto-resurrecting the empty collections and polluting DB
    audits. AuditLogger + BillingService stay always-on because they
    have live data (983 audit_log rows).
    """
    try:
        from shared.commercial import (
            get_workspace_service,
            get_audit_logger, get_billing_service,
        )

        async def safe_ensure_indexes(service, name):
            try:
                await service.ensure_indexes()
            except Exception as e:
                logger.warning(f"[AUREM] {name} index creation skipped: {e}")

        # Always-on (live data flowing through these).
        await safe_ensure_indexes(get_workspace_service(db), "WorkspaceService")
        await safe_ensure_indexes(get_audit_logger(db), "AuditLogger")
        await safe_ensure_indexes(get_billing_service(db), "BillingService")

        commercial_enabled = os.environ.get(
            "AUREM_COMMERCIAL_FEATURES", "0"
        ).lower() in ("1", "true", "yes")

        if commercial_enabled:
            from shared.commercial import (
                get_token_vault, get_consent_tracker,
            )
            await safe_ensure_indexes(get_token_vault(db), "TokenVault")
            await safe_ensure_indexes(get_consent_tracker(db), "ConsentTracker")

            # Gmail service indexes
            try:
                from shared.commercial import get_gmail_service
                await safe_ensure_indexes(get_gmail_service(db), "GmailService")
            except ImportError:
                pass

            # Unified Inbox indexes
            try:
                from shared.commercial.unified_inbox_service import get_unified_inbox_service
                await safe_ensure_indexes(get_unified_inbox_service(db), "UnifiedInbox")
            except ImportError:
                pass

            # WhatsApp indexes
            try:
                from shared.commercial.whatsapp_service import get_whatsapp_service
                await safe_ensure_indexes(get_whatsapp_service(db), "WhatsApp")
            except ImportError:
                pass

            # Key Service indexes
            try:
                from shared.commercial.key_service import get_aurem_key_service
                await safe_ensure_indexes(get_aurem_key_service(db), "KeyService")
            except ImportError:
                pass
        else:
            logger.info(
                "[AUREM] commercial-scaffolding indexes skipped "
                "(AUREM_COMMERCIAL_FEATURES != 1)"
            )

        # Memory Tiers indexes (3-tier memory + execution plans)
        try:
            from services.memory_tiers import ensure_indexes as memory_ensure_indexes
            await memory_ensure_indexes()
            logger.info("[AUREM] Memory tiers indexes created")
        except Exception as e:
            logger.warning(f"[AUREM] Memory tiers indexes skipped: {e}")

        # Hermes Memory Agent indexes
        try:
            from services.hermes_memory_agent import ensure_indexes as hermes_ensure_indexes, set_db as set_hermes_db
            set_hermes_db(db)
            await hermes_ensure_indexes()
            logger.info("[AUREM] Hermes Memory Agent indexes created")
        except Exception as e:
            logger.warning(f"[AUREM] Hermes Memory Agent indexes skipped: {e}")

        logger.info("[AUREM] All commercial indexes created")
    except ImportError as e:
        logger.warning(f"[AUREM] Commercial indexes skipped: {e}")


async def ensure_indexes(db):
    """
    Run on every startup.
    Idempotent — safe to run repeatedly.
    Creates missing indexes, skips existing.
    """
    from pymongo import ASCENDING, DESCENDING

    # Standard indexes for any collection matching these field patterns
    standard_patterns = {
        "tenant_id": [("tenant_id", ASCENDING)],
        "timestamp": [("timestamp", DESCENDING)],
        "status": [("status", ASCENDING)],
    }

    collections = await db.list_collection_names()
    created = 0

    for col_name in collections:
        col = db[col_name]
        existing = await col.index_information()

        sample = await col.find_one({})
        if not sample:
            continue

        # Auto-create standard indexes if field exists and index missing
        for field, index_spec in standard_patterns.items():
            if field in sample:
                direction = "1" if index_spec[0][1] == ASCENDING else "-1"
                index_name = f"{field}_{direction}"
                if index_name not in existing:
                    try:
                        await col.create_index(index_spec, background=True)
                        created += 1
                    except Exception:
                        pass

        # Auto TTL index for collections with expires_at field
        if "expires_at" in sample and "expires_at_ttl" not in existing:
            try:
                await col.create_index(
                    [("expires_at", ASCENDING)],
                    expireAfterSeconds=0,
                    name="expires_at_ttl",
                    background=True,
                )
                created += 1
            except Exception:
                pass

    indexed = 0
    for c in collections:
        idxs = await db[c].index_information()
        if len(idxs) > 1:
            indexed += 1
    pct = round(indexed / max(len(collections), 1) * 100, 1)
    logger.info(f"[INDEX] Auto-index complete: +{created} new | {indexed}/{len(collections)} indexed ({pct}%)")


async def init_aurem_redis():
    """Initialize AUREM Redis services (Memory, Cache, RateLimiter, WebSocket)."""
    try:
        from shared.commercial import (
            get_aurem_memory, get_semantic_cache,
            get_rate_limiter, get_websocket_hub,
        )
        await get_aurem_memory()
        await get_semantic_cache()
        await get_rate_limiter()
        await get_websocket_hub()
        logger.info("[AUREM] Redis services initialized")
    except ImportError as e:
        logger.warning(f"[AUREM] Redis services not initialized: {e}")


def start_agent_reach_crawler(db):
    """Start hourly Agent-Reach crawler (auto-feeds Vector DB)."""
    try:
        from services.agent_reach_service import set_db as set_crawler_db, hourly_crawler_loop
        set_crawler_db(db)
        asyncio.create_task(hourly_crawler_loop())
        logger.info("[AUREM] Agent-Reach Crawler started")
    except ImportError:
        pass


# ═══════════════════════════════════════════════
# BACKGROUND SCHEDULER FUNCTIONS
# ═══════════════════════════════════════════════

async def daily_digest_scheduler():
    """Background task that sends daily review digest at 9 AM EST (14:00 UTC)."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 14
            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if now.hour >= target_hour:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Daily digest scheduled in {wait_seconds/3600:.1f} hours")
            await asyncio.sleep(wait_seconds)
            from routes.orders import send_daily_review_digest
            await send_daily_review_digest()
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Daily digest scheduler error: {e}")
            await asyncio.sleep(3600)


async def aurem_morning_scheduler(db):
    """
    AUREM Master Morning Scheduler — runs every day at 7 AM EST (12:00 UTC).
    Launches all customer-facing daily workflows:
      1. Daily Intel digests (Tavily → Resend, CASL double-opt-in only)
      2. Trial lifecycle tick (Day-7 downgrades, Day-3 reminders)
      3. Morning brief generation for each tenant
    First fire: next 7 AM EST after service starts. Never fires multiple times per day.
    """
    logger.info("[AUREM-MORNING] Scheduler started — will fire daily at 7 AM EST (12:00 UTC)")
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 12  # 7 AM EST = 12:00 UTC (ignoring DST; EDT would be 11:00)
            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(
                f"[AUREM-MORNING] Next fire: {next_run.isoformat()} ({wait_seconds/3600:.1f} hours)"
            )
            await asyncio.sleep(wait_seconds)

            # ── 1. Daily Intel digests ──
            try:
                from routers.daily_intel_router import run_daily_intel_batch
                sent = await run_daily_intel_batch()
                logger.info(f"[AUREM-MORNING] Daily Intel: {sent} digests sent")
            except Exception as e:
                logger.warning(f"[AUREM-MORNING] Daily Intel skipped: {e}")

            # ── 2. Trial lifecycle tick ──
            try:
                from services.trial_scheduler import run_trial_scheduler_tick
                await run_trial_scheduler_tick(db)
                logger.info("[AUREM-MORNING] Trial scheduler tick complete")
            except Exception as e:
                logger.warning(f"[AUREM-MORNING] Trial tick skipped: {e}")

            # ── 3. Morning brief dispatch ──
            try:
                from services.morning_brief import run_morning_brief
                result = await run_morning_brief()
                logger.info(f"[AUREM-MORNING] Morning Brief generated: {result.get('brief_id', 'n/a') if isinstance(result, dict) else 'ok'}")
            except Exception as e:
                logger.warning(f"[AUREM-MORNING] Morning Brief skipped: {e}")

            # Debounce so we don't run twice in the same minute if clock jumps
            await asyncio.sleep(120)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[AUREM-MORNING] Scheduler error: {e}")
            await asyncio.sleep(1800)


async def operational_alerts_scheduler():
    """Daily operational alerts at 8 AM EST (13:00 UTC) - low stock, NPN expiry."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 13
            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if now.hour >= target_hour:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())
            try:
                from routes.orders import check_low_stock_alerts, check_npn_expiry_reminders
                await check_low_stock_alerts()
                await check_npn_expiry_reminders()
            except ImportError:
                pass
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[SCHEDULER] Operational alerts error: {e}")
            await asyncio.sleep(3600)


# Storefront-specific schedulers removed (iter 322h) — kept as no-op stubs
# so Pillar workers that reference them don't blow up.
async def abandoned_cart_scheduler():
    """Deprecated stub — routes.abandoned_cart_automation deleted iter 322h."""
    return


async def day21_review_scheduler():
    """Deprecated stub — routes.reviews_module deleted iter 322h."""
    return


async def whatsapp_crm_scheduler():
    """WhatsApp CRM actions daily at 10:30 AM EST (15:30 UTC)."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 15
            next_run = now.replace(hour=target_hour, minute=30, second=0, microsecond=0)
            if now.hour >= target_hour or (now.hour == target_hour and now.minute >= 30):
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())
            try:
                from routes.whatsapp_templates import check_day_messages
                import server
                total = 0
                for day in [0, 7, 14, 21, 25, 28, 35]:
                    count = await check_day_messages(server.db, day)
                    total += count
                logger.info(f"[SCHEDULER] WhatsApp CRM: {total} actions created")
            except ImportError:
                pass
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[SCHEDULER] WhatsApp CRM error: {e}")
            await asyncio.sleep(3600)


async def birthday_bonus_scheduler():
    """Deprecated stub — birthday bonus depended on routes.loyalty_bonuses (deleted iter 322h)."""
    return


async def orchestrator_digest_scheduler():
    """Orchestrator daily digest at 8 AM EST (13:00 UTC)."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            target_hour = 13
            next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
            if now.hour >= target_hour:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())
            try:
                from services.orchestrator import send_daily_digest
                await send_daily_digest()
            except ImportError:
                pass
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[SCHEDULER] Orchestrator digest error: {e}")
            await asyncio.sleep(3600)


async def auto_repair_scheduler():
    """Autonomous self-repair every 10 minutes."""
    await asyncio.sleep(120)  # Wait 2 min for DB to fully initialize
    while True:
        try:
            from services.auto_repair import run_autonomous_repair, _db as repair_db
            if repair_db is None:
                logger.info("[AUTO_REPAIR] Database not yet available, waiting...")
                await asyncio.sleep(60)
                continue
            result = await run_autonomous_repair()
            if result.get('status') == 'completed':
                auto_fixed = len(result.get('auto_fixed', []))
                ai_actions = len(result.get('ai_actions', []))
                if auto_fixed > 0 or ai_actions > 0:
                    logger.info(f"[AUTO_REPAIR] {auto_fixed} auto-fixed, {ai_actions} AI actions")
            await asyncio.sleep(600)
        except Exception as e:
            logger.error(f"[AUTO_REPAIR] Scheduler error: {e}")
            await asyncio.sleep(300)


async def monthly_data_cleanup_scheduler():
    """Monthly data cleanup on 1st of month at 2 AM EST (GDPR compliance)."""
    import pytz
    est = pytz.timezone('America/Toronto')
    await asyncio.sleep(120)
    logger.info("[SCHEDULER] Monthly data cleanup scheduler started")
    while True:
        try:
            now = datetime.now(est)
            if now.day == 1 and now.hour < 2:
                target = now.replace(hour=2, minute=0, second=0, microsecond=0)
            else:
                if now.month == 12:
                    target = now.replace(year=now.year + 1, month=1, day=1, hour=2, minute=0, second=0, microsecond=0)
                else:
                    target = now.replace(month=now.month + 1, day=1, hour=2, minute=0, second=0, microsecond=0)
            await asyncio.sleep((target - now).total_seconds())
            from routes.data_security_routes import run_monthly_data_cleanup
            result = await run_monthly_data_cleanup()
            if result.get("success"):
                logger.info(f"[SCHEDULER] Monthly cleanup: {result.get('total_deleted', 0)} records deleted")
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[SCHEDULER] Monthly cleanup error: {e}")
            await asyncio.sleep(86400)


def start_all_background_schedulers(db):
    """Launch all background scheduler tasks. Call from startup_event."""
    # Pillar 2 (Billing/Onboarding) schedulers now owned by pillars/billing/worker.py.
    # These 4 used to live in the generic schedulers list below; extracting them
    # removes 4 more potential event-loop blockers (Stripe, SMTP, cart webhooks).
    try:
        from pillars.billing.worker import start_pillar2_worker
        p2_summary = start_pillar2_worker(
            db,
            abandoned_cart_coro_factory=abandoned_cart_scheduler,
            day21_coro_factory=day21_review_scheduler,
            birthday_coro_factory=birthday_bonus_scheduler,
            aurem_morning_coro_factory=lambda: aurem_morning_scheduler(db),
        )
        print(
            f"[STARTUP] ✓ Pillar 2 worker online — {p2_summary['started_count']} schedulers, "
            f"{p2_summary['failed_count']} failed",
            flush=True,
        )
    except Exception as e:
        print(f"[STARTUP] ✗ Pillar 2 worker NOT started: {e}", flush=True)

    # Pillar 4 (Command Hub / Observability / Platform Ops) — 17 schedulers
    # isolated into pillars/command_hub/worker.py. Ye sab platform-wide
    # observability, audit, reporting, and ops loops hain jo pehle main
    # event loop pe tike the. Ab isolated task group mein chalte hain.
    try:
        from pillars.command_hub.worker import start_pillar4_worker
        p4_summary = start_pillar4_worker(
            db,
            daily_digest_coro_factory=daily_digest_scheduler,
            operational_alerts_coro_factory=operational_alerts_scheduler,
            whatsapp_crm_coro_factory=whatsapp_crm_scheduler,
            orchestrator_digest_coro_factory=orchestrator_digest_scheduler,
            auto_repair_coro_factory=auto_repair_scheduler,
            monthly_cleanup_coro_factory=monthly_data_cleanup_scheduler,
            daily_client_scan_coro_factory=_daily_client_scan_loop,
            health_score_coro_factory=lambda: _health_score_scheduler(db),
        )
        print(
            f"[STARTUP] ✓ Pillar 4 worker online — {p4_summary['started_count']} schedulers, "
            f"{p4_summary['failed_count']} failed",
            flush=True,
        )
    except Exception as e:
        print(f"[STARTUP] ✗ Pillar 4 worker NOT started: {e}", flush=True)

    # Sentinel Self-Healing Loop
    # NOTE: sentinel_router was moved to _archive/. We now use sentinel_anomaly_router + sentinel_client_router.
    # This stays as a guarded ImportError so old deployments don't regress.
    try:
        from routers.sentinel_router import start_sentinel  # noqa: F401
        start_sentinel()
        logger.info("[STARTUP] Sentinel Loop started (60s cycle)")
    except ImportError:
        logger.info("[STARTUP] Sentinel loop not wired (sentinel_router archived — using sentinel_anomaly_router instead)")
    except Exception as e:
        logger.warning(f"[STARTUP] Sentinel not started: {e}")

    # Pillar 1 (Sales) schedulers — auto_blast, proactive_outreach, news_monitor
    # are now owned by pillars/sales/worker.py. This removes the "single event
    # loop death spiral": a slow WHAPI/Twilio call in auto_blast no longer
    # blocks the 234 HTTP routers.
    try:
        from pillars.sales.worker import start_pillar1_worker
        p1_summary = start_pillar1_worker(
            db,
            news_monitor_coro_factory=lambda: _news_monitor_scheduler(db),
        )
        print(
            f"[STARTUP] ✓ Pillar 1 worker online — {p1_summary['started_count']} schedulers, "
            f"{p1_summary['failed_count']} failed",
            flush=True,
        )
    except Exception as e:
        print(f"[STARTUP] ✗ Pillar 1 worker NOT started: {e}", flush=True)

    # Auto-Heal, Auto-Repair, QA Bot (pulse + deep), Health Score, System Audit,
    # Daily Site Audit, Daily Client Scan, Autonomy Nightly Audit, Daily Digests,
    # Operational Alerts, WhatsApp CRM, Monthly Data Cleanup, Backup Loop,
    # ClawChief trio, Accurate-Scout Reverification — now all owned by
    # pillars/command_hub/worker.py (Pillar 4, attached above).

    # Shannon Runner + Self-Repair + Self-Scan are now handled by the
    # Pillar 3 worker (pillars/site_monitor/worker.py) — isolated task group
    # so a slow scheduler call doesn't block the 234 HTTP routers.
    try:
        from pillars.site_monitor.worker import start_pillar3_worker
        p3_summary = start_pillar3_worker(db)
        print(
            f"[STARTUP] ✓ Pillar 3 worker online — {p3_summary['started_count']} schedulers, "
            f"{p3_summary['failed_count']} failed",
            flush=True,
        )
    except Exception as e:
        print(f"[STARTUP] ✗ Pillar 3 worker NOT started: {e}", flush=True)

    # News Monitor moved to Pillar 1 worker (pillars/sales/worker.py).
    # Site Monitor moved to Pillar 3 worker (pillars/site_monitor/worker.py).

    # One-time migration (iter 263) — remove legacy dry_run fields & statuses
    # left over from the removed Dry Run system. Idempotent — safe to run every
    # startup; a no-op once cleaned.
    async def _dry_run_cleanup_migration():
        try:
            r1 = await db.agent_state.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
            r2 = await db.agent_config.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
            r3 = await db.campaign_leads.update_many({"status": "dry_run"}, {"$set": {"status": "new"}})
            r4 = await db.campaign_leads.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
            r5 = await db.hunt_commands.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
            r6 = await db.agent_feed.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
            touched = (r1.modified_count + r2.modified_count + r3.modified_count +
                       r4.modified_count + r5.modified_count + r6.modified_count)
            if touched:
                logger.info(f"[STARTUP] Dry-run cleanup migration: {touched} docs updated")
        except Exception as e:
            logger.warning(f"[STARTUP] Dry-run cleanup migration skipped: {e}")
    _safe_task(_dry_run_cleanup_migration(), "dry_run_cleanup_migration")

    # iter 268 — one-time backfill: infer lifecycle_stage for legacy leads so
    # the Kanban board shows them in the correct column (not all "New").
    # Idempotent — only touches docs missing/empty lifecycle_stage.
    async def _lifecycle_backfill_migration():
        try:
            from services.lead_lifecycle import backfill_lifecycle_stages
            result = await backfill_lifecycle_stages(db, dry_run=False)
            if result.get("updated", 0) > 0:
                logger.info(f"[STARTUP] Lifecycle backfill: {result['updated']} leads → {result['counts']}")
        except Exception as e:
            logger.warning(f"[STARTUP] Lifecycle backfill skipped: {e}")
    _safe_task(_lifecycle_backfill_migration(), "lifecycle_backfill_migration")

    # iter 290 — Pixel install reminder loop
    _safe_task(_pixel_install_reminder_loop(db), "pixel_install_reminder_loop")

    # iter 291 — Day-6 trial expiry email
    _safe_task(_trial_expiry_reminder_loop(db), "trial_expiry_reminder_loop")

    logger.info("[STARTUP] All background schedulers launched")


async def _daily_client_scan_loop():
    """Run daily client website scans at 3:15 AM UTC (after self-scan)."""
    await asyncio.sleep(180)  # Wait for startup
    while True:
        try:
            now = datetime.now(timezone.utc)
            target = now.replace(hour=3, minute=15, second=0, microsecond=0)
            if now.hour > 3 or (now.hour == 3 and now.minute >= 15):
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info(f"[CLIENT-SCAN] Next run in {wait/3600:.1f} hours")
            await asyncio.sleep(wait)
            from utils.self_scan import run_daily_client_scans
            await run_daily_client_scans()
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[CLIENT-SCAN] Scheduler error: {e}")
            await asyncio.sleep(3600)

    logger.info("[STARTUP] All background schedulers launched")


async def _health_score_scheduler(db):
    """
    Health Score Engine scheduler.
    - Runs immediately for polaris-built-001 on deploy
    - Then recalculates ALL active tenants every 6 hours
    """
    INTERVAL_HOURS = 6

    await asyncio.sleep(15)  # Let other services initialize

    # Immediate run for polaris-built-001
    try:
        from services.health_score_engine import calculate_health_score, recalculate_all
        result = await calculate_health_score(db, "polaris-built-001")
        logger.info(f"[HealthScore] Initial polaris-built-001: {result.get('health_score', 0)}/100")
    except Exception as e:
        logger.warning(f"[HealthScore] Initial polaris run failed: {e}")

    # Recurring loop — every 6 hours
    while True:
        try:
            await asyncio.sleep(INTERVAL_HOURS * 3600)
            from services.health_score_engine import recalculate_all
            result = await recalculate_all(db)
            logger.info(f"[HealthScore] Scheduled recalculation: {result.get('recalculated', 0)} tenants")
        except Exception as e:
            logger.error(f"[HealthScore] Scheduler error: {e}")
            await asyncio.sleep(600)  # Retry in 10 minutes


async def _news_monitor_scheduler(db):
    """
    News Auto-Monitor scheduler.
    - Runs immediately on deploy
    - Then fetches news every 2 hours
    """
    INTERVAL_HOURS = 2

    await asyncio.sleep(300)  # 5 min — let startup fully stabilize before hitting DDG

    # Immediate run
    try:
        from services.news_monitor import fetch_news
        result = await fetch_news(db)
        logger.info(f"[NewsMonitor] Initial fetch: {result.get('new_articles', 0)} articles, {result.get('lead_matches', 0)} leads")
    except Exception as e:
        logger.warning(f"[NewsMonitor] Initial fetch failed: {e}")

    # Recurring loop
    while True:
        try:
            await asyncio.sleep(INTERVAL_HOURS * 3600)
            from services.news_monitor import fetch_news
            result = await fetch_news(db)
            logger.info(f"[NewsMonitor] Scheduled fetch: {result.get('new_articles', 0)} articles, {result.get('lead_matches', 0)} leads")
        except Exception as e:
            logger.error(f"[NewsMonitor] Scheduler error: {e}")
            await asyncio.sleep(600)


async def _pixel_install_reminder_loop(db):
    """
    iter 290 — Onboarding pixel install reminders.
    Every 5 minutes scan aurem_onboarding for tenants where pixel_installed != True
    and send Resend email at 5min mark + ORA SMS at 24h mark.
    """
    import httpx
    await asyncio.sleep(120)  # let startup settle
    INTERVAL = 5 * 60  # 5 minutes
    while True:
        try:
            now = datetime.now(timezone.utc)
            cursor = db.aurem_onboarding.find(
                {"pixel_installed": {"$ne": True}, "started_at": {"$exists": True}},
                {"_id": 0, "tenant_id": 1, "email": 1, "phone": 1, "business_name": 1,
                 "started_at": 1, "pixel_email_sent_at": 1, "pixel_sms_sent_at": 1, "domain": 1}
            )
            async for onb in cursor:
                try:
                    started = onb.get("started_at")
                    if isinstance(started, str):
                        started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        # Ensure tz-aware so subtraction with `now` doesn't TypeError
                        if started_dt.tzinfo is None:
                            started_dt = started_dt.replace(tzinfo=timezone.utc)
                    else:
                        continue
                    age = (now - started_dt).total_seconds()
                    tenant_id = onb["tenant_id"]
                    email = onb.get("email") or ""
                    business = onb.get("business_name") or "there"

                    # 5-min reminder email (once)
                    if age >= 300 and not onb.get("pixel_email_sent_at") and email:
                        api_key = os.environ.get("RESEND_API_KEY", "")
                        if api_key:
                            snippet = (
                                f'<script src="{os.environ.get("PUBLIC_API_ORIGIN","https://aurem.live")}/api/pixel/aurem-pixel.js" '
                                f'data-aurem-key="{tenant_id}" async></script>'
                            )
                            html = (
                                f"<p>Hey {business},</p>"
                                f"<p>One last step — paste this in your site's <code>&lt;head&gt;</code> tag to activate auto-fixes:</p>"
                                f"<pre style='background:#f5f5f5;padding:12px;border-radius:6px;font-size:12px'>{snippet}</pre>"
                                f"<p>Or use the WordPress plugin (one-click): "
                                f"<a href='https://aurem.live/api/pixel/wp-plugin/{tenant_id}.zip'>Download WP plugin</a></p>"
                                f"<p>— ORA, AUREM</p>"
                            )
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as c:
                                    await c.post(
                                        "https://api.resend.com/emails",
                                        headers={"Authorization": f"Bearer {api_key}",
                                                 "Content-Type": "application/json"},
                                        json={
                                            "from": os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>"),
                                            "to": [email],
                                            "subject": "Activate AUREM — paste this snippet (30 seconds)",
                                            "html": html,
                                        },
                                    )
                                await db.aurem_onboarding.update_one(
                                    {"tenant_id": tenant_id},
                                    {"$set": {"pixel_email_sent_at": now.isoformat()}},
                                )
                            except Exception as e:
                                logger.warning(f"[pixel-reminder] email failed for {tenant_id}: {e}")

                    # 24h reminder SMS (once)
                    if age >= 86400 and not onb.get("pixel_sms_sent_at") and onb.get("phone"):
                        try:
                            from services.twilio_service import send_sms
                            msg = (
                                f"AUREM here — your auto-fix pixel still isn't installed on {onb.get('domain') or 'your site'}. "
                                f"Reply YES and we'll install it for you. Or one-click WP plugin: "
                                f"https://aurem.live/api/pixel/wp-plugin/{tenant_id}.zip"
                            )
                            await send_sms(onb["phone"], msg)
                            await db.aurem_onboarding.update_one(
                                {"tenant_id": tenant_id},
                                {"$set": {"pixel_sms_sent_at": now.isoformat()}},
                            )
                        except Exception as e:
                            logger.warning(f"[pixel-reminder] sms failed for {tenant_id}: {e}")
                except Exception as e:
                    logger.warning(f"[pixel-reminder] per-tenant error: {e}")
        except Exception as e:
            logger.error(f"[pixel-reminder] loop error: {e}")
        await asyncio.sleep(INTERVAL)




async def _trial_expiry_reminder_loop(db):
    """
    iter 291 — Day-6 trial expiry email.
    Once per hour scans aurem_onboarding for trials ~6 days old that haven't
    been notified, sends "your trial ends tomorrow" email via Resend.
    """
    import httpx
    await asyncio.sleep(180)
    INTERVAL = 60 * 60  # 1 hour
    while True:
        try:
            now = datetime.now(timezone.utc)
            d6 = (now - timedelta(days=6)).isoformat()
            d7 = (now - timedelta(days=7)).isoformat()
            cursor = db.aurem_onboarding.find(
                {"started_at": {"$lte": d6, "$gte": d7},
                 "trial_expiry_email_sent_at": {"$exists": False}},
                {"_id": 0, "tenant_id": 1, "email": 1, "business_name": 1, "domain": 1}
            )
            api_key = os.environ.get("RESEND_API_KEY", "")
            from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")
            async for onb in cursor:
                if not (api_key and onb.get("email")):
                    continue
                try:
                    business = onb.get("business_name") or "there"
                    # iter 282g — use branded HTML template
                    try:
                        from services.brand_emails import render_trial_ending
                        user_doc = {
                            "first_name": (onb.get("first_name")
                                           or business.split(" ")[0]),
                            "business_name": business,
                            "email": onb.get("email"),
                        }
                        # Pull this-week stats (best-effort — defaults if empty)
                        issues_fixed = int(onb.get("issues_fixed_7d") or 0)
                        score_delta = int(onb.get("score_delta_7d") or 0)
                        uptime_pct = float(onb.get("uptime_pct_7d") or 100.0)
                        html = render_trial_ending(
                            user_doc,
                            issues_fixed=issues_fixed,
                            score_delta=score_delta,
                            uptime_pct=uptime_pct,
                        )
                    except Exception as _render_err:
                        logger.debug(f"[trial-expiry] branded render failed: {_render_err}")
                        html = (
                            f"<p>Hey {business},</p>"
                            f"<p><strong>Your AUREM trial ends tomorrow.</strong></p>"
                            f"<p>Add a card to keep your fixes running. One click. Cancel any time.</p>"
                            f"<p><a href='https://aurem.live/my/billing?upgrade=1' "
                            f"style='display:inline-block;padding:12px 22px;background:#F97316;color:#0A0A00;"
                            f"text-decoration:none;font-weight:700'>Keep my fixes running &rarr;</a></p>"
                        )
                    async with httpx.AsyncClient(timeout=10.0) as c:
                        r = await c.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            json={
                                "from": from_addr,
                                "to": [onb["email"]],
                                "subject": "Your AUREM trial ends tomorrow \u2014 keep your fixes",
                                "html": html,
                            },
                        )
                        r.raise_for_status()
                    await db.aurem_onboarding.update_one(
                        {"tenant_id": onb["tenant_id"]},
                        {"$set": {"trial_expiry_email_sent_at": now.isoformat()}},
                    )
                    logger.info(f"[trial-expiry] day-6 email sent to {onb['email']}")
                except Exception as e:
                    logger.warning(f"[trial-expiry] send failed for {onb.get('email')}: {e}")
        except Exception as e:
            logger.error(f"[trial-expiry] loop error: {e}")
        await asyncio.sleep(INTERVAL)
