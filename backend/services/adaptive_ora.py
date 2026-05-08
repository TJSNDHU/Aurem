"""
Adaptive ORA Halting — P3 Automation Mode
==========================================

Inspired by OpenMythos's Adaptive Computation Time (ACT) halting, translated
from neural loops to business agent loops.

Each lead carries a Conviction Score. Signals from WhatsApp/Site/Voice bump the
score up; inactivity/bounces/opt-outs push it down. Bucket determines the next
agent and timing.

MODES (persisted in db.adaptive_ora_config):
  SHADOW     — compute + store + broadcast, NO agent actions fire. (safe default)
  AUTOMATION — when a lead crosses into CLOSER_NOW, hand it to closer_ora and
               wake the agent immediately. When a lead drops into HALT, mark
               stage=halted + status=do_not_contact so follow-up and closer
               both skip it (saves Twilio/LLM spend on dead leads).

Buckets (higher score = hotter lead):
  90+   CLOSER_NOW   — call personally; alert admin via WhatsApp
  70-89 INTENSIFY    — send offer + urgency message within 30 min
  40-69 CONTINUE     — standard drip cadence (24h)
  20-39 SLOW         — weekly drip only
  <20   HALT         — stop spending, mark dormant
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# ─── Tunables (can be overridden per-tenant later) ────────────────────────
DECAY_ALPHA = 0.85      # how much of previous score carries over on each signal
SCORE_FLOOR = -20.0
SCORE_CEIL  = 100.0
INITIAL_SCORE = 20.0    # every new lead starts "mildly interested"
HISTORY_KEEP = 50       # capped conviction_history entries per lead

MODE_SHADOW = "shadow"
MODE_AUTOMATION = "automation"
_MODE_CACHE: Dict[str, Any] = {"mode": MODE_SHADOW, "loaded_at": 0.0}

# (floor, bucket, next_agent, delay_after_signal)
BUCKETS: list[Tuple[float, str, Optional[str], Optional[timedelta]]] = [
    (90.0,  "CLOSER_NOW",  "closer_ora",   timedelta(minutes=2)),
    (70.0,  "INTENSIFY",   "followup_ora", timedelta(minutes=30)),
    (40.0,  "CONTINUE",    "followup_ora", timedelta(hours=24)),
    (20.0,  "SLOW",        "followup_ora", timedelta(days=7)),
    (-1e9,  "HALT",        None,            None),
]

SIGNAL_WEIGHTS: Dict[str, float] = {
    # Positive signals
    "site_visit":             25.0,
    "site_dwell_60s":         15.0,
    "site_return":            20.0,
    "whatsapp_read":          10.0,
    "whatsapp_reply":         40.0,
    "whatsapp_reply_intent":  30.0,   # keywords like price/yes/kab/cost
    "missed_call":            35.0,
    "booking_click":          50.0,
    "email_open":              8.0,
    "email_click":            25.0,
    # Negative signals
    "no_response_48h":       -15.0,
    "silent_7d":             -10.0,
    "opt_out":              -100.0,
    "bounce":                -20.0,
    "whatsapp_block":        -80.0,
}

INTENT_KEYWORDS = [
    "price", "cost", "how much", "kitna", "kitne", "rate", "pricing", "plan",
    "yes", "interested", "ok", "kab", "when", "tell me", "book", "demo",
    "meeting", "call me", "haan", "theek",
]


def compute_bucket(score: float) -> Tuple[str, Optional[str], Optional[timedelta]]:
    """Map a numeric score to (bucket_name, next_agent, delay)."""
    for floor, name, agent, delay in BUCKETS:
        if score >= floor:
            return name, agent, delay
    return "HALT", None, None


def classify_reply_intent(text: str) -> bool:
    """Return True if the reply text contains purchase-intent keywords."""
    if not text:
        return False
    t = text.lower()
    return any(kw in t for kw in INTENT_KEYWORDS)


# ═════════════════════════════════════════════════════════════════════
# MODE MANAGEMENT (persisted in db.adaptive_ora_config)
# ═════════════════════════════════════════════════════════════════════
import time as _time  # localized import to avoid polluting top-level
_MODE_CACHE_TTL = 10.0  # seconds — re-read config at most every 10s


async def get_mode(db) -> str:
    """Return current operating mode ('shadow' or 'automation'). Cached 10s."""
    now = _time.time()
    if _MODE_CACHE.get("mode") and (now - _MODE_CACHE.get("loaded_at", 0)) < _MODE_CACHE_TTL:
        return _MODE_CACHE["mode"]
    try:
        doc = await db.adaptive_ora_config.find_one({"_id": "singleton"}, {"_id": 0, "mode": 1})
        mode = (doc or {}).get("mode") or MODE_SHADOW
    except Exception as e:
        logger.debug(f"[AdaptiveORA] mode read failed, defaulting to shadow: {e}")
        mode = MODE_SHADOW
    if mode not in (MODE_SHADOW, MODE_AUTOMATION):
        mode = MODE_SHADOW
    _MODE_CACHE["mode"] = mode
    _MODE_CACHE["loaded_at"] = now
    return mode


async def set_mode(db, mode: str, actor: Optional[str] = None) -> str:
    """Persist operating mode. Returns the stored mode (validated)."""
    if mode not in (MODE_SHADOW, MODE_AUTOMATION):
        raise ValueError(f"invalid mode: {mode}")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.adaptive_ora_config.update_one(
        {"_id": "singleton"},
        {
            "$set": {"mode": mode, "updated_at": now_iso, "updated_by": actor or "system"},
            "$push": {"history": {"$each": [{"mode": mode, "at": now_iso, "actor": actor}], "$slice": -50}},
        },
        upsert=True,
    )
    _MODE_CACHE["mode"] = mode
    _MODE_CACHE["loaded_at"] = _time.time()
    logger.info(f"[AdaptiveORA] mode switched to {mode} by {actor or 'system'}")
    return mode


async def _auto_act_on_transition(
    db,
    lead: Dict[str, Any],
    new_score: float,
    new_bucket: str,
    prev_bucket: Optional[str],
) -> Optional[str]:
    """
    Fire the appropriate side-effect when a lead transitions buckets.
    Only invoked when get_mode() == AUTOMATION.

    Returns a short human-readable action name, or None if nothing fired.
    """
    lead_id = lead.get("lead_id")
    if not lead_id:
        return None

    # ── HOT: hand to closer and wake it immediately ───────────────────
    if new_bucket == "CLOSER_NOW" and prev_bucket != "CLOSER_NOW":
        stage = lead.get("stage")
        if stage == "handed_to_closer":
            return None  # already there, don't double-wake
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "stage": "handed_to_closer",
                    "handed_to_closer_at": datetime.now(timezone.utc).isoformat(),
                    "handed_to_closer_reason": f"adaptive_ora score>={new_score:.0f}",
                }},
            )
        except Exception as e:
            logger.warning(f"[AdaptiveORA] closer handoff DB write failed for {lead_id}: {e}")
            return None

        # Notify closer via A2A bus + wake agent in the background
        try:
            from services.a2a_bus import bus
            await bus.emit(
                "adaptive_ora",
                "hot_lead_closer",
                {"lead_id": lead_id, "score": new_score, "business_name": lead.get("business_name")},
                to_agent="closer_ora",
            )
        except Exception as e:
            logger.debug(f"[AdaptiveORA] bus emit failed: {e}")

        try:
            from services.agents import get_agent
            agent = get_agent("closer_ora")
            if agent is not None and not getattr(agent, "paused", False):
                # Run in background so the webhook/API caller returns immediately
                asyncio.create_task(agent.run_cycle())
        except Exception as e:
            logger.debug(f"[AdaptiveORA] closer wake failed: {e}")

        return "closer_handoff"

    # ── COLD: halt to save spend ──────────────────────────────────────
    if new_bucket == "HALT" and prev_bucket != "HALT":
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "stage": "halted",
                    "status": "do_not_contact",
                    "halted_at": datetime.now(timezone.utc).isoformat(),
                    "halted_reason": f"adaptive_ora score<20 ({new_score:.0f})",
                }},
            )
        except Exception as e:
            logger.warning(f"[AdaptiveORA] halt write failed for {lead_id}: {e}")
            return None
        return "halted"

    return None


async def record_signal(
    db,
    lead_id: str,
    signal: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a lead's conviction score based on a signal.

    P1 SHADOW MODE: writes to db.campaign_leads but does NOT schedule or fire
    any agents. next_agent / next_run_at fields are set for operator visibility
    only — the existing fixed pipeline (followup_listener) is unchanged.

    Args:
        db: Motor MongoDB client
        lead_id: document id (lead_id field, not _id)
        signal: key from SIGNAL_WEIGHTS
        meta: optional debug context attached to the history entry

    Returns:
        dict with new score + bucket, or None if lead not found / signal unknown
    """
    weight = SIGNAL_WEIGHTS.get(signal)
    if weight is None:
        logger.debug(f"[AdaptiveORA] Unknown signal '{signal}' — ignored")
        return None

    try:
        lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    except Exception as e:
        logger.warning(f"[AdaptiveORA] DB read failed for {lead_id}: {e}")
        return None
    if not lead:
        return None

    now = datetime.now(timezone.utc)
    prev_score = float(lead.get("conviction_score", INITIAL_SCORE))
    prev_bucket = lead.get("conviction_bucket") or compute_bucket(prev_score)[0]

    # Cheap cost penalty to discourage unbounded spend on a single lead.
    # Only subtract on negative-or-neutral signals — don't penalize hot responses.
    cost_penalty = 0.0
    if weight <= 0:
        cost = (
            float(lead.get("llm_tokens_spent", 0)) * 0.00003
            + float(lead.get("messages_sent", 0)) * 0.005
            + float(lead.get("voice_minutes", 0)) * 0.02
        )
        cost_penalty = min(cost, 5.0)

    new_score = (DECAY_ALPHA * prev_score) + weight - cost_penalty
    new_score = max(SCORE_FLOOR, min(SCORE_CEIL, new_score))

    bucket, next_agent, delay = compute_bucket(new_score)
    next_run = (now + delay).isoformat() if delay else None

    history_entry = {
        "at": now.isoformat(),
        "score": round(new_score, 1),
        "prev": round(prev_score, 1),
        "delta": round(new_score - prev_score, 1),
        "reason": f"{'+' if weight >= 0 else ''}{weight:g} {signal}",
        **({"meta": meta} if meta else {}),
    }

    try:
        await db.campaign_leads.update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "conviction_score": round(new_score, 1),
                    "conviction_bucket": bucket,
                    "next_agent": next_agent,
                    "next_run_at": next_run,
                    "last_signal_at": now.isoformat(),
                    "last_signal": signal,
                },
                "$push": {
                    "conviction_history": {
                        "$each": [history_entry],
                        "$slice": -HISTORY_KEEP,
                    }
                },
            },
        )
    except Exception as e:
        logger.warning(f"[AdaptiveORA] DB write failed for {lead_id}: {e}")
        return None

    logger.info(
        f"[AdaptiveORA] {lead_id[:24]} · {signal} · "
        f"{prev_score:.1f} → {new_score:.1f} · bucket={bucket}"
    )

    # ── AUTOMATION MODE: act on bucket transitions ────────────────────
    mode = await get_mode(db)
    action_fired: Optional[str] = None
    if mode == MODE_AUTOMATION and bucket != prev_bucket:
        action_fired = await _auto_act_on_transition(db, lead, new_score, bucket, prev_bucket)

    # Fire SSE so Console live feed shows score changes.
    try:
        from routers.agents_router import _broadcast_feed  # existing helper
        mode_tag = "🤖" if mode == MODE_AUTOMATION else "👁"
        action_tag = f" · ▶ {action_fired}" if action_fired else ""
        await _broadcast_feed(
            "adaptive_ora",
            f"{mode_tag} {lead.get('business_name','?')[:30]} · {signal} · "
            f"score {prev_score:.0f}→{new_score:.0f} · {bucket}{action_tag}",
            "warning" if action_fired else "info",
        )
    except Exception:
        pass  # feed is optional

    return {
        "lead_id": lead_id,
        "business_name": lead.get("business_name"),
        "prev_score": round(prev_score, 1),
        "new_score": round(new_score, 1),
        "prev_bucket": prev_bucket,
        "bucket": bucket,
        "next_agent": next_agent,
        "next_run_at": next_run,
        "signal": signal,
        "mode": mode,
        "action_fired": action_fired,
    }


async def init_lead_conviction(db, lead_id: str, score: float = INITIAL_SCORE) -> None:
    """
    Seed a newly discovered lead with an initial conviction score.
    Safe to call on existing leads — only sets fields that don't already exist.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "conviction_score": {"$exists": False}},
            {
                "$set": {
                    "conviction_score": round(float(score), 1),
                    "conviction_bucket": compute_bucket(score)[0],
                    "conviction_seeded_at": now,
                    "last_signal_at": now,
                    "last_signal": "lead_created",
                },
                "$setOnInsert": {"conviction_history": []},
            },
        )
    except Exception as e:
        logger.debug(f"[AdaptiveORA] seed skipped for {lead_id}: {e}")


async def backfill_missing_scores(db, limit: int = 5000) -> int:
    """
    One-shot: seed conviction_score on every existing lead that doesn't have one.
    Safe to re-run; idempotent. Returns number of leads updated.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    res = await db.campaign_leads.update_many(
        {"conviction_score": {"$exists": False}},
        {
            "$set": {
                "conviction_score": INITIAL_SCORE,
                "conviction_bucket": compute_bucket(INITIAL_SCORE)[0],
                "conviction_seeded_at": now_iso,
                "last_signal_at": now_iso,
                "last_signal": "backfill_init",
            }
        },
    )
    return int(res.modified_count)


async def top_leads(db, limit: int = 20) -> list[Dict[str, Any]]:
    """Hot leads ranked by score — for admin heat map."""
    cursor = db.campaign_leads.find(
        {"conviction_score": {"$exists": True}},
        {
            "_id": 0,
            "lead_id": 1,
            "business_name": 1,
            "city": 1,
            "category": 1,
            "conviction_score": 1,
            "conviction_bucket": 1,
            "next_agent": 1,
            "next_run_at": 1,
            "last_signal": 1,
            "last_signal_at": 1,
        },
    ).sort("conviction_score", -1).limit(int(limit))
    return [r async for r in cursor]
