"""
AUREM router registry — LEAN-mode configuration (extracted iter 322m+).

Pulled out of `registry.py` (which had grown past 2200 LOC) so the
allow/skip logic that gates router registration in production is owned
in one small, testable module.

Public API
----------
- ``LEAN_MODE`` — bool snapshot of the env at import time.
- ``SKIP_IN_LEAN`` — frozenset of module paths to skip when LEAN is on.
- ``make_should_skip(lean_mode)`` — returns a `should_skip(path)` fn that
  matches both ``routers.xxx`` and bare ``xxx`` forms.

Behaviour is byte-identical to the old inline block — this module exists
purely to shrink ``registry.py`` and to make the skip list reviewable on
its own.
"""
from __future__ import annotations

import os
from typing import Callable

# True when AUREM_ENV=production OR LEAN_ROUTES=1.
LEAN_MODE: bool = (
    os.environ.get("AUREM_ENV") == "production"
    or os.environ.get("LEAN_ROUTES") == "1"
)


# Routers that are NOT needed for core AUREM SaaS platform.
# Cross-referenced against frontend fetch() calls — only skip routers
# with 0 frontend refs.
SKIP_IN_LEAN: frozenset[str] = frozenset({
    # ── E-commerce inline (575+ routes) ──
    "auth_inline", "product_inline", "cart_inline", "order_inline",
    "payment_inline", "admin_inline", "influencer_inline",
    "store_settings_inline", "analytics_inline", "subscriber_inline",
    "seo_inline", "shipping_qr_inline", "blog_inline",
    "founding_inline", "postal_inline",
    # ── Removed heavy deps (chromadb/playwright/onnx) ──
    "routers.browser_agent_router", "routers.vector_search_router",
    "routers.document_scanner_router", "routers.document_rag_router",
    "routers.semantic_router", "routers.monitoring_router",
    # ── Not configured (needs API keys not present) ──
    "routers.video_generation_router", "routers.ai_email_router",
    "routers.sms_alerts_router",
    # "routers.whatsapp_alerts" — RE-ENABLED (iter 285): wired to WhatsApp Integration sidebar widget
    "routers.whatsapp_router", "routers.whatsapp_webhook_router",
    "routers.gmail_router", "routers.gmail_channel_router",
    "routers.omnidim_router", "routers.connector_router",
    # "routers.universal_connector_router" — RE-ENABLED (iter 327h):
    # The AUREM tracking pixel (static/aurem-pixel.js:44) hits
    # /api/universal/webhooks/generic on every page view of every
    # customer who installs the pixel. With LEAN_ROUTES=1 this router
    # was skipped → every visitor event 404'd → silent data loss.
    # The "generic" platform path needs zero API keys (it just inserts
    # into db.universal_events). Stripe/Shopify/Woocommerce paths
    # gracefully fall back to "skip signature check" when the secret
    # env var is missing, so it's safe to keep loaded in LEAN mode.
    # "routers.google_oauth_router" — RE-ENABLED (iter 285): wired to Gmail Integration sidebar widget + audit
    "routers.shopify_storefront_router",
    # iter 322ee — e-commerce skeleton dead-load (orders/products/carts
    # all empty + AUREM is SaaS, not Shopify). Lean-mode skip — files
    # kept for tests + future opt-in. Saves N route registrations on
    # cold start and removes ~2200 lines of dead router code from the
    # production OpenAPI schema.
    "routers.shopify_pulse_router",
    "routers.attribution_engine",
    # ── Internal / background-only (0 frontend refs) ──
    "routers.orchestrator_brain_router", "routers.ooda_loop_router",
    "routers.agent_harness_router",
    "routers.critic_router",
    "routers.self_healing_router", "routers.deployment_router_api",
    "routers.crash_dashboard_router", "routers.site_audit_router",
    "routers.agent_health_router", "routers.tenant_optimization_router",
    "routers.tenant_migration_router", "routers.tenant_router",
    "routers.owner_panel_router", "routers.security_router",
    # ── Not active / not launched (0 frontend refs) ──
    # "routers.smart_search_router",  # UNBLOCKED for Scout
    # "routers.soc2_compliance_router" — RE-ENABLED (iter 285.4): wired to SOC2ComplianceDashboard sidebar widget
    "routers.hooks_router",
    # "routers.generative_ui_router" — RE-ENABLED (iter 280.4): wired 5
    # dashboards (subscription/agent_logs/billing/errors/deployments) to
    # live Mongo; remaining 8 expose `data_source: mock|partial|static` flag.
    "routers.sentiment_analysis_router", "routers.intent_router",
    "routers.custom_subscription_router", "routers.subscription_public_router",
    # iter 315f — admin_plan_management UNBLOCKED: powers /admin/plans page
    # (AdminPlanManager.jsx) which calls /api/admin/plans/all + custom/pricing.
    # Was previously in the skip list, causing 404s + Auth modal stuck.
    # "routers.admin_plan_management",
    "routers.billing_router", "routers.pricing_router", "routers.refund_router",
    "routers.compliance_router", "routers.compliance_framework_router",
    "routers.data_governance_router", "routers.email_automation_router",
    "routers.inbox_router", "routers.ticket_router", "routers.live_support",
    "routers.appointment_router", "routers.partner_portal_router",
    "routers.referral_portal_router",
    "routers.a2a_learning_router", "routers.a2a_protocol_router",
    "routers.mcp_router",
    "routers.daily_digest_router",
    # ── NEW: Zero frontend references (cross-checked with grep) ──
    "routers.unified_inbox_router",    # 11 routes, 0 refs
    "routers.brain_router",            # 6 routes, 0 refs
    "routers.agent_reach_router",      # 10 routes, 0 refs
    "routers.digest_routes",           # 6 routes, 0 refs
    # lead_enrichment_router — now wired to Lead Pipeline Enrich buttons (keep loaded)
    "routers.session_memory_router",   # 2 routes, 0 refs
    "routers.action_engine_router",    # 5 routes, 0 refs
    "routers.honeypot_router",         # 7 routes, internal
    "routers.aurem_llm_proxy_router",  # 4 routes, 0 refs
    "routers.super_admin_analytics_router",  # 2 routes, 0 refs
    "routers.github_integration",      # 11 routes, 0 refs
    "routers.batch_router",            # 4 routes, 0 refs
    "routers.biometric_auth",          # 12 routes, legacy /biometric prefix (not /api/biometric)
    "routers.aurem_ai_router",         # 3 routes, 0 refs
    # ── NEW: Zero-ref routes/* modules ──
    "routes.chat_widget_routes",       # 15 routes, 0 refs
    "routes.email_routes",             # 8 routes, 0 refs
    "routes.content_routes",           # 6 routes, 0 refs
    "routes.a2a_routes",               # 3 routes, 0 refs
    "routes.site_audit_routes",        # 6 routes, 0 refs
    "routes.data_security_routes",     # 4 routes, 0 refs
    # ── NEW: Standalone blocks — user confirmed safe to skip ──
    "routers.nexus_router",            # 6 routes, backlogged
    "routers.z_image_router",          # 4 routes, backlogged
    # "routers.proximity_blast_router" — RE-ENABLED (iter 284): wired to ProximityBlast.jsx sidebar widget
    # "routers.system_pulse_router" — WIRED to SystemPulseHUD.jsx (keep loaded)
    "routers.crypto_signal_engine",    # separate deployment
    # "routers.appointment_scheduler_router" — RE-ENABLED (iter 327h):
    # P1 task ships Google Calendar event creation + confirmation
    # email at lines 171,172. Router must be loaded in LEAN mode
    # for the booking endpoint to serve traffic.
    # ── Core sub-modules with 0 frontend refs ──
    "routes.business_system",          # 33 routes (CRM/inventory/accounting/fulfillment)
    "routes.automation_gaps_routes",   # 0 refs
    # "routers.server_misc_routes" — RE-ENABLED: hosts the SSE endpoint (/api/admin/events/{id})
    # required by Hunt Live Progress, ORA chat streaming, and Empire HUD events.
    "routers.pwa_router",             # PWA not deployed, 14 routes
})


def make_should_skip(lean_mode: bool) -> Callable[[str], bool]:
    """Build a `should_skip(module_path)` predicate.

    The predicate matches the module string in three forms:
      - exact match in `SKIP_IN_LEAN`
      - with a `routers.` prefix prepended
      - with a `routers.` prefix stripped

    When `lean_mode` is False the predicate always returns False — i.e.
    every router gets registered. This mirrors the original inline
    helper's behaviour.
    """
    skip_set = SKIP_IN_LEAN

    def _should_skip(module_path: str) -> bool:
        if not lean_mode:
            return False
        return (
            module_path in skip_set
            or f"routers.{module_path}" in skip_set
            or module_path.replace("routers.", "") in skip_set
        )

    return _should_skip
