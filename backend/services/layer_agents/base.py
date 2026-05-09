"""
base.py — `LayerAgent` base + 8 layer specs registered into the A2A bus.
═══════════════════════════════════════════════════════════════════════════
On import, each layer subscribes to its A2A topics. The bus calls back
with the event payload — agent records a learning row + emits a follow-up
event to the BIN ORA telemetry channel.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# Layer registry — keyed by layer_id, with topics + keyword routing
LAYERS: Dict[str, Dict[str, Any]] = {
    "L1_identity": {
        "name": "Identity & Auth",
        "topics": ["auth.login", "auth.signup", "auth.2fa", "auth.password_reset"],
        "keywords": ["login", "sign in", "password", "2fa", "auth", "register"],
    },
    "L2_plan": {
        "name": "Plan & Subscription",
        "topics": ["plan.change", "plan.upgrade", "plan.cancel", "subscription.created"],
        "keywords": ["plan", "subscription", "upgrade", "downgrade", "cancel"],
    },
    "L3_billing": {
        "name": "Stripe & Billing",
        "topics": ["billing.invoice", "billing.payment_failed", "billing.refund"],
        "keywords": ["invoice", "payment", "card", "billing", "refund", "charge"],
    },
    "L4_trial": {
        "name": "Trial Lifecycle",
        "topics": ["trial.started", "trial.reminder", "trial.expired"],
        "keywords": ["trial", "demo", "free", "expired", "days left"],
    },
    "L5_gate": {
        "name": "Service Gating",
        "topics": ["service.locked", "service.quota_exceeded", "service.usage"],
        "keywords": ["locked", "quota", "limit", "402", "429", "upgrade"],
    },
    "L6_data": {
        "name": "BIN Data Isolation",
        "topics": ["data.export", "data.delete", "data.access"],
        "keywords": ["export", "delete", "privacy", "gdpr", "my data"],
    },
    "L7_usage": {
        "name": "Usage Metering",
        "topics": ["usage.reported", "usage.threshold_hit"],
        "keywords": ["usage", "consumption", "how much", "leftover"],
    },
    "L8_experience": {
        "name": "Frontend / UX",
        "topics": ["ux.error", "ux.feedback", "ux.confused"],
        "keywords": ["confused", "broken", "ui", "feedback", "stuck", "help"],
    },
}


def route_keyword_to_layer(question: str) -> str:
    q = (question or "").lower()
    best = ("L8_experience", 0)
    for lid, spec in LAYERS.items():
        score = sum(1 for kw in spec["keywords"] if kw in q)
        if score > best[1]:
            best = (lid, score)
    return best[0]


async def record_layer_event(db, layer_id: str, business_id: str, event: str,
                              payload: Dict[str, Any]) -> None:
    """Persist a layer event for later aggregation by admin ORA."""
    if db is None:
        return
    try:
        import hashlib
        import os
        salt = os.environ.get("ADMIN_ORA_HASH_SALT", "aurem-default-salt")
        bin_hash = hashlib.sha256(f"{salt}:{business_id}".encode()).hexdigest()[:16]
        await db.admin_ora_brain.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "layer_event",
            "layer": layer_id,
            "layer_name": LAYERS.get(layer_id, {}).get("name", layer_id),
            "event": event,
            "bin_hash": bin_hash,
            "payload_keys": sorted(list((payload or {}).keys()))[:10],
        })
    except Exception as e:
        logger.debug(f"[layer_agents] record event failed: {e}")


def initialize_layer_agents(bus) -> int:
    """Hook each LAYER's topics into the A2A bus. Returns number of
    subscriptions registered. Idempotent — safe to call multiple times."""
    if bus is None:
        return 0
    count = 0
    for lid, spec in LAYERS.items():
        for topic in spec["topics"]:
            try:
                # Bus subscribe API may vary — best-effort with fallback.
                if hasattr(bus, "subscribe"):
                    bus.subscribe(topic, _make_handler(lid))
                    count += 1
            except Exception:
                pass
    logger.info(f"[layer_agents] initialized {count} A2A subscriptions across {len(LAYERS)} layers")
    return count


def _make_handler(layer_id: str):
    """Bind the layer_id into a closure so the handler knows which layer
    it belongs to."""
    async def _handle(event_name: str, payload: Dict[str, Any]):
        try:
            from server import db
            bin_id = (payload or {}).get("business_id") or (payload or {}).get("tenant_id") or ""
            await record_layer_event(db, layer_id, bin_id, event_name, payload or {})
        except Exception as e:
            logger.debug(f"[layer_agents:{layer_id}] handler error: {e}")
    return _handle
