"""
AUREM MongoDB Index Optimization Script
========================================
Brings index coverage from 30.6% to 70%+ across 186 collections.

Priority tiers:
  P0: User-specified priority + OODA hot path
  P1: High-volume (>100 docs) unindexed
  P2: All collections with tenant_id/timestamp/status fields
"""
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("index_optimizer")


# ═══════════════════════════════════════════════════════════════════
# INDEX DEFINITIONS — organized by priority tier
# ═══════════════════════════════════════════════════════════════════

INDEXES = {
    # ─── P0: USER PRIORITY COLLECTIONS ────────────────────────────
    "approval_patterns": [
        ([("tenant_id", ASCENDING), ("action_type", ASCENDING)], {}),
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "self_improvement": [
        ([("tenant_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
        ([("cycle_id", ASCENDING)], {}),
        ([("pattern_id", ASCENDING), ("status", ASCENDING)], {}),
    ],

    # Additional indexes for already-indexed priority collections
    "knowledge_base": [
        ([("tenant_id", ASCENDING), ("type", ASCENDING), ("target_stages", ASCENDING)], {}),
    ],
    "leads": [
        ([("tenant_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("tenant_id", ASCENDING), ("score", DESCENDING)], {}),
    ],
    "pipeline_runs": [
        ([("tenant_id", ASCENDING), ("final_status", ASCENDING)], {}),
        ([("run_id", ASCENDING)], {"unique": True}),
    ],
    "episodic_memory": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "audit_chain": [
        ([("agent_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("sequence", DESCENDING)], {}),
    ],

    # ─── P0: OODA PIPELINE HOT PATH ──────────────────────────────
    "pipeline_completions": [
        ([("tenant_id", ASCENDING), ("completed_at", DESCENDING)], {}),
        ([("run_id", ASCENDING)], {}),
    ],
    "known_fixes": [
        ([("issue_pattern", ASCENDING)], {}),
    ],
    "pipeline_states": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
        ([("pipeline_id", ASCENDING)], {}),
    ],
    "semantic_cache": [
        ([("tenant_id", ASCENDING), ("query_hash", ASCENDING)], {}),
        ([("created_ts", ASCENDING)], {"expireAfterSeconds": 86400}),
    ],
    "system_config": [
        ([("config_key", ASCENDING)], {"unique": True}),
    ],
    "origin_commits": [
        ([("user_id", ASCENDING), ("committed_at", DESCENDING)], {}),
    ],
    "git_backup_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("status", ASCENDING)], {}),
    ],
    "site_audits": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],

    # ─── P1: HIGH-VOLUME UNINDEXED (>100 docs) ───────────────────
    "live_patches": [
        ([("business_id", ASCENDING), ("category", ASCENDING)], {}),
        ([("batch_id", ASCENDING)], {}),
        ([("status", ASCENDING)], {}),
    ],
    "auto_heal_runs": [
        ([("timestamp", DESCENDING)], {}),
        ([("overall_status", ASCENDING)], {}),
    ],
    "heartbeats": [
        ([("timestamp", DESCENDING)], {}),
        ([("alert_level", ASCENDING)], {}),
    ],
    "system_auto_repairs": [
        ([("tenant_id", ASCENDING), ("scanned_at", DESCENDING)], {}),
        ([("site_url", ASCENDING)], {}),
    ],
    "deployment_log": [
        ([("tenant_id", ASCENDING), ("deployed_at", DESCENDING)], {}),
        ([("business_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("batch_id", ASCENDING)], {}),
    ],
    "crawler_logs": [
        ([("crawl_timestamp", DESCENDING)], {}),
    ],
    "auto_repair_log": [
        ([("timestamp", DESCENDING)], {}),
        ([("system_healthy_after", ASCENDING)], {}),
    ],
    "sentinel_verifications": [
        ([("timestamp", DESCENDING)], {}),
        ([("service", ASCENDING), ("verified", ASCENDING)], {}),
    ],
    "cost_savings_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("model_used", ASCENDING)], {}),
    ],
    "sentinel_alerts": [
        ([("timestamp", DESCENDING)], {}),
        ([("type", ASCENDING), ("service", ASCENDING)], {}),
    ],
    "aurem_bug_history": [
        ([("timestamp", DESCENDING)], {}),
        ([("system_healthy_after", ASCENDING)], {}),
    ],
    "repair_fixes": [
        ([("user_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("scan_url", ASCENDING), ("category", ASCENDING)], {}),
    ],

    # ─── P2: MEDIUM-VOLUME WITH QUERYABLE FIELDS ─────────────────
    "crash_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("type", ASCENDING)], {}),
    ],
    "search_history": [
        ([("timestamp", DESCENDING)], {}),
    ],
    "scan_sessions": [
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "autotune_usage_log": [
        ([("session_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "approval_queue": [
        ([("tenant_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "malicious_events": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("score", DESCENDING)], {}),
    ],
    "revenue_forecasts": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "security_events": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("severity", ASCENDING)], {}),
    ],
    "vault_audit_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
        ([("user_id", ASCENDING), ("action", ASCENDING)], {}),
    ],
    "customer_website_fixes": [
        ([("user_id", ASCENDING), ("status", ASCENDING)], {}),
    ],
    "repair_deployments": [
        ([("user_id", ASCENDING), ("status", ASCENDING)], {}),
    ],
    "offer_sets": [
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "revenue_events": [
        ([("created_at", DESCENDING)], {}),
        ([("type", ASCENDING)], {}),
    ],
    "payment_transactions": [
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {}),
        ([("payment_status", ASCENDING)], {}),
    ],
    "shadow_test_results": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "anomaly_detections": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "deals": [
        ([("status", ASCENDING), ("stage", ASCENDING)], {}),
        ([("created_at", DESCENDING)], {}),
    ],
    "shared_reports": [
        ([("share_id", ASCENDING)], {"unique": True}),
        ([("user_id", ASCENDING)], {}),
    ],
    "api_keys": [
        ([("tenant_id", ASCENDING), ("active", ASCENDING)], {}),
        ([("key_id", ASCENDING)], {"unique": True}),
    ],
    "negotiation_sessions": [
        ([("tenant_id", ASCENDING), ("status", ASCENDING)], {}),
    ],
    "tone_sync_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "contacts": [
        ([("status", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "ghost_actions": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "ucp_negotiations": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "ora_action_logs": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "sent_messages": [
        ([("tenant_id", ASCENDING), ("channel", ASCENDING)], {}),
    ],
    "tracking_links": [
        ([("tenant_id", ASCENDING), ("clicked", ASCENDING)], {}),
        ([("ref_id", ASCENDING)], {}),
    ],
    "deep_scout_log": [
        ([("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "connector_data": [
        ([("platform", ASCENDING), ("fetched_at", DESCENDING)], {}),
    ],
    "business_profiles": [
        ([("user_id", ASCENDING)], {}),
    ],

    # ─── P2: LOW-VOLUME BUT FREQUENTLY QUERIED ───────────────────
    "approval_settings": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "brief_settings": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "tenant_personas": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "tenant_settings": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "whitelabel_settings": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "onboarding": [
        ([("user_id", ASCENDING)], {"unique": True}),
    ],
    "local_llm_config": [
        ([("enabled", ASCENDING)], {}),
    ],
    "sentinel_dashboard": [
        ([("status", ASCENDING)], {}),
    ],
    "tenant_optimization_profiles": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "tenant_optimization_reports": [
        ([("tenant_id", ASCENDING), ("generated_at", DESCENDING)], {}),
    ],
    "voice_profiles": [
        ([("user_id", ASCENDING)], {"unique": True}),
    ],
    "referral_profiles": [
        ([("user_id", ASCENDING)], {"unique": True}),
        ([("referral_code", ASCENDING)], {"unique": True}),
    ],
    "crypto_treasury_config": [
        ([("tenant_id", ASCENDING)], {}),
    ],
    "crypto_wallets": [
        ([("wallet_id", ASCENDING)], {"unique": True}),
    ],
    "tenant_health": [
        ([("tenant_id", ASCENDING)], {}),
    ],
    "managed_clients": [
        ([("admin_user_id", ASCENDING)], {}),
    ],
    "invoices": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "payments": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "custom_subscriptions": [
        ([("user_id", ASCENDING), ("status", ASCENDING)], {}),
    ],
    "messages": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "recovery_queue": [
        ([("status", ASCENDING), ("send_at", ASCENDING)], {}),
    ],
    "recovery_campaigns": [
        ([("tenant_id", ASCENDING)], {}),
    ],
    "secret_vault": [
        ([("tenant_id", ASCENDING), ("user_id", ASCENDING)], {}),
    ],
    "sentinel_retries": [
        ([("service", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "service_registry": [
        ([("service_id", ASCENDING)], {"unique": True}),
    ],
    "ema_feedback": [
        ([("context", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "ema_profiles": [
        ([("context", ASCENDING)], {"unique": True}),
    ],
    "geo_checks": [
        ([("tenant_id", ASCENDING), ("query", ASCENDING)], {}),
    ],
    "subscription_plans": [
        ([("plan_id", ASCENDING)], {"unique": True}),
    ],
    "decision_makers": [
        ([("tenant_id", ASCENDING), ("company_domain", ASCENDING)], {}),
    ],
    "compliance_reports": [
        ([("report_id", ASCENDING)], {"unique": True}),
    ],
    "compliance_evidence": [
        ([("snapshot_id", ASCENDING)], {}),
    ],
    "migration_log": [
        ([("tenant_id", ASCENDING), ("ts", DESCENDING)], {}),
    ],
    "shopify_connections": [
        ([("tenant_id", ASCENDING), ("shop_domain", ASCENDING)], {}),
    ],
    "crm_connections": [
        ([("tenant_id", ASCENDING), ("status", ASCENDING)], {}),
    ],
    "crm_sync_jobs": [
        ([("tenant_id", ASCENDING), ("started_at", DESCENDING)], {}),
    ],
    "ora_chat_sessions": [
        ([("session_id", ASCENDING)], {"unique": True}),
    ],
    "ora_training_files": [
        ([("user_id", ASCENDING), ("source_type", ASCENDING)], {}),
    ],
    "swarm_executions": [
        ([("swarm_id", ASCENDING)], {}),
    ],
    "agent_executions": [
        ([("agent_id", ASCENDING), ("started_at", DESCENDING)], {}),
    ],
    "daily_summaries": [
        ([("date", DESCENDING)], {}),
    ],
    "ghost_briefs": [
        ([("tenant_id", ASCENDING)], {}),
    ],
    "push_deployments": [
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "team_members": [
        ([("tenant_id", ASCENDING), ("email", ASCENDING)], {}),
    ],
    "email_verification_tokens": [
        ([("token", ASCENDING)], {"unique": True}),
        ([("expires_at", ASCENDING)], {"expireAfterSeconds": 0}),
    ],
    "universal_events": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "universal_orders": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "nexus_credentials": [
        ([("tenant_id", ASCENDING), ("connector_id", ASCENDING)], {}),
    ],
    "platform_connections": [
        ([("tenant_id", ASCENDING), ("platform_type", ASCENDING)], {}),
    ],
    "tenant_documents": [
        ([("tenant_id", ASCENDING)], {}),
    ],
    "shopify_app_installs": [
        ([("shop_domain", ASCENDING)], {"unique": True}),
    ],
    "shopify_sync_jobs": [
        ([("tenant_id", ASCENDING), ("started_at", DESCENDING)], {}),
    ],
    "training_knowledge": [
        ([("category", ASCENDING)], {}),
    ],
    "usage_events": [
        ([("tenant_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "usage_tracking": [
        ([("tenant_id", ASCENDING), ("resource_type", ASCENDING)], {}),
    ],
    "crm_automations": [
        ([("status", ASCENDING)], {}),
    ],
    "attribution_links": [
        ([("ref_id", ASCENDING)], {"unique": True}),
    ],
    "attribution_events": [
        ([("ref_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "latency_pulse": [
        ([("session_id", ASCENDING), ("created_at", DESCENDING)], {}),
    ],
    "_unresolved_quarantine": [
        ([("tenant_id", ASCENDING), ("processed", ASCENDING)], {}),
    ],
    "a2a_learning_sessions": [
        ([("session_id", ASCENDING)], {}),
    ],
    "patch_errors": [
        ([("patch_id", ASCENDING), ("timestamp", DESCENDING)], {}),
    ],
    "payment_reminders": [
        ([("invoice_id", ASCENDING)], {}),
    ],
    "api_keys_registry": [
        ([("service_id", ASCENDING)], {}),
    ],
    "asvs_audits": [
        ([("audited_at", DESCENDING)], {}),
    ],
    "security_audits": [
        ([("audited_at", DESCENDING)], {}),
    ],
    "sentiment_analyses": [
        ([("analyzed_at", DESCENDING)], {}),
    ],
    "acquisition_config": [
        ([("tenant_id", ASCENDING)], {"unique": True}),
    ],
    "shopify_oauth_nonces": [
        ([("nonce", ASCENDING)], {"unique": True}),
        ([("created_at", ASCENDING)], {"expireAfterSeconds": 600}),
    ],
}


async def create_all_indexes():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["aurem_db"]

    total_created = 0
    total_skipped = 0
    total_failed = 0

    for coll_name, index_defs in INDEXES.items():
        existing = await db[coll_name].index_information()
        existing_keys = set()
        for idx_info in existing.values():
            key_tuple = tuple(tuple(k) for k in idx_info.get("key", []))
            existing_keys.add(key_tuple)

        for keys, options in index_defs:
            key_tuple = tuple(tuple(k) for k in keys)
            if key_tuple in existing_keys:
                total_skipped += 1
                continue

            try:
                name = await db[coll_name].create_index(keys, **options)
                total_created += 1
                logger.info(f"  CREATED {coll_name}.{name}")
            except Exception as e:
                total_failed += 1
                logger.warning(f"  FAILED {coll_name}: {e}")

    # Final count
    all_colls = await db.list_collection_names()
    indexed = 0
    for c in all_colls:
        idxs = await db[c].index_information()
        if len(idxs) > 1:
            indexed += 1

    pct = indexed / len(all_colls) * 100
    print(f"\n{'=' * 60}")
    print(f"INDEX OPTIMIZATION COMPLETE")
    print(f"  Created: {total_created}")
    print(f"  Skipped (already exist): {total_skipped}")
    print(f"  Failed: {total_failed}")
    print(f"  Coverage: {indexed}/{len(all_colls)} ({pct:.1f}%)")
    print(f"{'=' * 60}")

    client.close()


if __name__ == "__main__":
    asyncio.run(create_all_indexes())
