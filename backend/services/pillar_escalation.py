"""
pillar_escalation.py — Tiered autonomous escalation for pillar degradation.
═══════════════════════════════════════════════════════════════════════════

Hooks into `_check_p1_infrastructure` consecutive-fail counter and progressively
escalates through the existing A2A → Council → ORA stack:

  Tier 1 (1st fail / yellow)   → DIAGNOSE  : emit A2A, council deliberate,
                                              run Claude pillar diagnoser,
                                              prepare suggested fix
                                              (no-apply, just analysis)

  Tier 2 (2nd fail / yellow)   → AUTO-FIX  : push the prepared fix
                                              (motor topology refresh +
                                              breakers reset + cache invalidate),
                                              emit A2A, council ratify

  Tier 3 (3rd fail / red)      → DR SYNC   : trigger Atlas M0 mirror snapshot
                                              (db_backup_service.run_backup_async),
                                              record persistent_red in truth_ledger,
                                              broadcast outage event on A2A

All tiers fire FIRE-AND-FORGET via asyncio.create_task — never block the
health endpoint. Each tier records its own ORA learning row so the brain
ingests escalation history.

Rate-limit: each tier may only fire ONCE per `_RATE_LIMIT_SECONDS` window
to prevent cascading task creation when health is polled every 10s.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Per-(pillar, tier) last-fire timestamps (monotonic seconds). Was per-tier
# only — that incorrectly blocked P2's T1 if P1 had just fired its T1.
# iter 322 — keyed by (pillar, tier) so each pillar escalates independently.
_LAST_FIRED: Dict[tuple, float] = {}
_RATE_LIMIT_SECONDS = 60.0  # max one fire per (pillar, tier) per 60s


def _can_fire_for(tier: int, pillar_key: str) -> bool:
    now = time.monotonic()
    key = (pillar_key, tier)
    if (now - _LAST_FIRED.get(key, 0.0)) < _RATE_LIMIT_SECONDS:
        return False
    _LAST_FIRED[key] = now
    return True


# Backward-compat shim — older tests/imports referenced _can_fire(tier).
def _can_fire(tier: int) -> bool:
    return _can_fire_for(tier, "P1")


async def _emit_a2a(event: str, payload: Dict[str, Any]) -> None:
    try:
        from services.a2a_bus import bus
        await bus.emit(from_agent="pillar_monitor", event=event, payload=payload)
    except Exception as e:
        logger.debug(f"[pillar-escalation] A2A emit skipped ({event}): {e}")


async def _record_ora(db, tier: int, outcome: str, extra: Dict[str, Any]) -> None:
    if db is None:
        return
    try:
        await db.ora_brain_thoughts.insert_one({
            "type": "pillar_escalation",
            "source": "pillar_escalation_orchestrator",
            "tier": tier,
            "outcome": outcome,
            "extra": extra,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"[pillar-escalation] ora ingest skipped: {e}")


async def _council_deliberate(action: str, payload: Dict[str, Any]) -> str:
    """Wrap council.deliberate so failures don't block escalation."""
    try:
        from services.council_deliberate import deliberate
        result = await deliberate(
            action=action, agent="pillar_monitor",
            payload=payload, required=["qa", "security"], advisory=["casl"],
        )
        return result.get("verdict", "APPROVED")
    except Exception as e:
        logger.warning(f"[pillar-escalation] council unavailable ({action}): {e}")
        return "APPROVED"  # fail-open during outage


# ─── Tier 1 — Diagnose ──────────────────────────────────────────────────────
# Per-pillar Claude prompt context — root-cause hint depends on pillar type.
_PILLAR_DIAGNOSE_HINT = {
    "P1": ("Pillar P1 (Infrastructure / MongoDB). Likely cause: Atlas M0 burst-credit "
           "throttling, motor pool stale connection, or genuine network outage."),
    "P2": ("Pillar P2 (Intelligence / LLM gateway). Likely cause: provider rate-limit "
           "(OpenRouter/Groq/Anthropic/OpenAI), API key revoked, or breaker tripped "
           "after sustained 5xx from upstream."),
    "P3": ("Pillar P3 (Outreach / Email+SMS). Likely cause: Twilio A2P 10DLC "
           "throttling, Resend domain not verified, breaker open after delivery "
           "failures, or carrier-side block."),
    "P4": ("Pillar P4 (Revenue / Stripe). Likely cause: Stripe API key invalid "
           "(test vs live mismatch), webhook signature mismatch, or breaker open "
           "after charge failures / disputes spike."),
}


async def tier1_diagnose(db, pillar_key: str = "P1") -> None:
    """Yellow → diagnose: emit A2A, council deliberate, prepare a fix
    suggestion via the shared sentinel_ai_diagnose service. Stores a row in
    repair_suggestions tagged source='pillar_escalation_t1'.
    """
    if not _can_fire_for(1, pillar_key):
        return
    payload = {"pillar": pillar_key, "tier": 1, "phase": "diagnose"}
    await _emit_a2a("PILLAR_DEGRADED_T1_DIAGNOSE", payload)
    verdict = await _council_deliberate(f"pillar_t1_diagnose:{pillar_key}", payload)
    if verdict != "APPROVED":
        await _record_ora(db, 1, "council_rejected", {"verdict": verdict, "pillar": pillar_key})
        return

    hint = _PILLAR_DIAGNOSE_HINT.get(
        pillar_key, f"Pillar {pillar_key} reported transient health failure."
    )
    pseudo = {
        "error_id": f"pillar_{pillar_key}_t1_{int(time.time())}",
        "signature": f"pillar_{pillar_key}_degraded",
        "type": "pillar_degraded",
        "classification": f"pillar_{pillar_key.lower()}_degraded",
        "message": (
            f"{hint} Need root-cause diagnosis + actionable fix recommendation. "
            "Be specific about which subsystem to inspect."
        ),
        "status_code": 0,
        "url": "/api/pillars/health",
        "method": "INTERNAL",
        "stack": "",
        "page_url": "",
        "hostname": "aurem-backend",
    }
    try:
        from services.sentinel_ai_diagnose import diagnose_and_store
        suggestion = await diagnose_and_store(db, pseudo, source="pillar_escalation_t1")
        await _emit_a2a("ORA_PILLAR_DIAGNOSED", {
            "pillar": pillar_key, "tier": 1,
            "suggestion_id": (suggestion or {}).get("suggestion_id"),
            "severity": (suggestion or {}).get("severity"),
            "confidence": (suggestion or {}).get("confidence"),
        })
        await _record_ora(db, 1, "diagnosed", {
            "suggestion_id": (suggestion or {}).get("suggestion_id"),
            "pillar": pillar_key,
        })
        logger.info(f"[pillar-escalation] T1 diagnose complete for {pillar_key}")
    except Exception as e:
        logger.warning(f"[pillar-escalation] T1 diagnose failed: {e}")
        await _record_ora(db, 1, "diagnose_failed", {"error": str(e)[:160], "pillar": pillar_key})


# ─── Tier 2 — Auto-fix ──────────────────────────────────────────────────────
async def tier2_autofix(db, pillar_key: str = "P1") -> None:
    """Yellow → auto-fix. Pillar-aware safe repair sequence:
       P1 → motor topology refresh (forces Atlas reconnect)
       P2/P3/P4 → reset OPEN/half-open breakers relevant to that pillar
       ALL → invalidate pillars-health cache so next poll re-checks live
    """
    if not _can_fire_for(2, pillar_key):
        return
    payload = {"pillar": pillar_key, "tier": 2, "phase": "auto_fix"}
    await _emit_a2a("PILLAR_DEGRADED_T2_AUTOFIX", payload)
    verdict = await _council_deliberate(f"pillar_t2_autofix:{pillar_key}", payload)
    if verdict != "APPROVED":
        await _record_ora(db, 2, "council_rejected", {"verdict": verdict, "pillar": pillar_key})
        return

    repaired = False
    actions: list = []

    # P1-only: motor topology refresh (forces Atlas reconnect)
    if pillar_key == "P1" and db is not None:
        try:
            client = getattr(db, "client", None)
            if client is not None:
                await asyncio.wait_for(client.list_database_names(), timeout=6.0)
                await asyncio.wait_for(db.command("ping"), timeout=3.0)
                actions.append("mongo_topology_refresh")
                repaired = True
        except Exception as e:
            logger.warning(f"[pillar-escalation] T2 motor refresh failed: {e}")
            actions.append(f"mongo_refresh_failed:{type(e).__name__}")

    # P2/P3/P4: reset only the breakers relevant to this pillar.
    # P1 ALSO benefits from this when Atlas issues tripped mongodb_breaker.
    pillar_breaker_hints = {
        "P1": ("mongo",),
        "P2": ("openrouter", "groq", "anthropic", "openai"),
        "P3": ("twilio", "resend"),
        "P4": ("stripe",),
    }
    relevant = pillar_breaker_hints.get(pillar_key, ())
    try:
        from services.breakers import ALL_BREAKERS
        reset_count = 0
        for b in ALL_BREAKERS:
            try:
                if not relevant or any(r in b.name.lower() for r in relevant):
                    if getattr(b, "current_state", "") in ("open", "half_open"):
                        b.close()
                        reset_count += 1
            except Exception:
                pass
        if reset_count:
            actions.append(f"breakers_reset:{reset_count}")
            if pillar_key != "P1":  # for non-P1, breaker reset = repair
                repaired = True
    except Exception as e:
        logger.debug(f"[pillar-escalation] breaker reset skipped: {e}")

    # Invalidate the pillar-health cache so the next poll re-checks live
    try:
        from routers.pillars_health_router import _cache as _ph_cache
        _ph_cache["ts"] = 0.0
        _ph_cache["data"] = None
        actions.append("cache_invalidated")
    except Exception:
        pass

    # Persist the fix attempt
    if db is not None:
        try:
            await db.repair_requests.insert_one({
                "pillar": pillar_key,
                "kind": "pillar_t2_autofix",
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": "pillar_escalation_orchestrator",
                "status": "repaired" if repaired else "best_effort",
                "actions": actions,
            })
        except Exception:
            pass

    outcome = "auto_repaired" if repaired else "best_effort"
    await _emit_a2a(f"PILLAR_T2_{outcome.upper()}", {
        "pillar": pillar_key, "actions": actions, "repaired": repaired,
    })
    await _record_ora(db, 2, outcome, {"actions": actions, "pillar": pillar_key})
    logger.info(f"[pillar-escalation] T2 autofix complete for {pillar_key}: {actions}")


# ─── Tier 3 — Outage protection ─────────────────────────────────────────────
async def tier3_dr_sync(db, pillar_key: str = "P1") -> None:
    """Red → outage protection. Pillar-aware:
       P1 → DR mirror snapshot (data is at risk)
       P2/P3/P4 → record persistent_red + outage broadcast (data not at risk,
                  but operators must be alerted to switch to fallback channels)
    """
    if not _can_fire_for(3, pillar_key):
        return
    payload = {"pillar": pillar_key, "tier": 3, "phase": "outage_protection"}
    await _emit_a2a("PILLAR_OUTAGE_T3", payload)
    # Outage protection bypasses normal council gating.
    await _council_deliberate(f"pillar_t3:{pillar_key}", payload)

    backup_outcome = "skipped_non_p1"
    if pillar_key == "P1":
        try:
            from services.db_backup_service import run_backup_async

            async def _bg_backup():
                try:
                    res = await run_backup_async(triggered_by="pillar_t3_outage")
                    logger.info(f"[pillar-escalation] T3 DR backup result: {res}")
                except Exception as e:
                    logger.warning(f"[pillar-escalation] T3 DR backup failed: {e}")

            asyncio.create_task(_bg_backup())
            backup_outcome = "queued"
        except Exception as e:
            logger.warning(f"[pillar-escalation] T3 DR backup not available: {e}")
            backup_outcome = f"unavailable:{type(e).__name__}"

    # Truth ledger persistent_red entry — applies to ALL pillars
    try:
        from services import truth_ledger
        await truth_ledger.record_persistent_red(
            actor="pillar_escalation_t3",
            description=f"{pillar_key} declared OUTAGE after 3 consecutive failures",
            evidence={"pillar": pillar_key, "tier": 3, "backup_outcome": backup_outcome},
            outcome="outage_dispatched",
        )
    except Exception as e:
        logger.debug(f"[pillar-escalation] truth_ledger record skipped: {e}")

    await _emit_a2a("PILLAR_T3_OUTAGE_DISPATCHED", {
        "pillar": pillar_key, "backup_outcome": backup_outcome,
    })
    await _record_ora(db, 3, "outage_dispatched", {
        "pillar": pillar_key, "backup_outcome": backup_outcome,
    })
    logger.info(f"[pillar-escalation] T3 outage handler complete for {pillar_key}")


# ─── Public dispatcher ──────────────────────────────────────────────────────
def schedule_escalation(db, pillar_key: str, consecutive_fails: int) -> None:
    """Fire-and-forget tier dispatcher. Called from `_check_p1_infrastructure`
    when a fail cycle increments the counter. Never blocks, never raises.
    """
    if consecutive_fails <= 0:
        return
    tier = min(consecutive_fails, 3)
    handler = {1: tier1_diagnose, 2: tier2_autofix, 3: tier3_dr_sync}.get(tier)
    if handler is None:
        return
    try:
        asyncio.create_task(handler(db, pillar_key))
    except RuntimeError:
        # No running loop (e.g., unit test) — safe to skip.
        pass
