"""
plan_enforcement.py — DEPRECATED SHIM (iter 322w)
═════════════════════════════════════════════════
Per the iter 322w consolidation, all plan/service/usage logic now lives
in `services.subscription_manager`. This module re-exports the legacy
function names so existing service-level callers keep working.

⚠️ NEW CODE: import from `services.subscription_manager` directly. The
canonical entry point is `get_plan_state(business_id)`.

Routers were migrated; service-level callers (e.g.
`services/content_engine.py`, `services/plan_resolver.py`) still hit
this shim for backwards compatibility.
"""
from services.subscription_manager import (  # noqa: F401
    set_db,
    get_tenant_plan,
    check_action_limit,
    check_pipeline_limit,
    check_feature_access,
    get_usage_summary,
    get_usage,
    increment_usage,
    seed_plans,
    get_plan_state,
)

# Legacy PLAN_TIERS dict — some old code reads this directly. Provide a
# minimal projection from the SSOT so the shape stays stable.
try:
    from aurem_config.plans import PLANS as _SSOT_PLANS
    PLAN_TIERS = {
        plan_id: {
            "tier": plan_id,
            "name": p.get("name", plan_id.title()),
            "price_cad": p.get("price_cad", 0),
            "limits": p.get("limits", {}),
            "services": p.get("services", []),
        }
        for plan_id, p in _SSOT_PLANS.items()
    }
except Exception:
    PLAN_TIERS = {}
