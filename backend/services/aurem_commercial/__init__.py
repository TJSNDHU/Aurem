"""SHIM — AUREM Commercial package migrated to `shared.commercial`.
All existing imports continue to work via this re-export.
"""
from shared.commercial import *  # noqa: F401,F403
# Re-export submodules so `from services.aurem_commercial.X import Y` still works
from shared.commercial import (  # noqa: F401
    encryption_service, audit_service, token_vault, workspace_service,
    consent_service, billing_service, gmail_service, redis_memory,
    semantic_cache, rate_limiter, websocket_hub, agent_reach,
    mapping_service, omnidim_service, whatsapp_service, date_parser,
    unified_inbox_service, key_service, a2a_handoff_service,
    brain_orchestrator, voice_service, usage_service, llm_proxy,
    action_engine,
)
