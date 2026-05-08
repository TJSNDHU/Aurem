"""
Smart Approval Engine — Hybrid Auto/Manual Decision System
Powers Stage 5 (Human Loop) of the AUREM Pipeline.

Decision types:
  AUTO        — executes immediately, logged
  AUTO_CANCEL — executes after countdown, cancellable via STOP
  MANUAL      — queued, requires explicit YES/NO
  BLOCKED     — held for admin review
"""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════════════════
# DEFAULT RULES
# ═══════════════════════════════════════

DEFAULT_SETTINGS = {
    "invoice_auto_limit": 500,
    "vip_threshold": 85,
    "auto_approve_hours": [9, 18],
    "bulk_outreach_limit": 10,
    "pattern_learning_enabled": True,
    "pattern_threshold": 20,
    "rules": {
        "seo_fix": "auto",
        "css_fix": "auto",
        "pixel_css_fix": "auto",
        "lead_score_update": "auto",
        "cache_warm": "auto",
        "knowledge_sync": "auto",
        "sentiment_analysis": "auto",
        "message_draft": "auto_log",
        "invoice_reminder": "conditional",
        "lead_outreach": "conditional",
        "vip_outreach": "manual",
        "config_change": "manual",
        "data_delete": "manual",
        "payment_trigger": "manual",
        "bulk_outreach": "conditional",
        "queue_outreach": "conditional",
        "send_reminder": "conditional",
        "seo_meta_fix": "auto",
        "inject_css": "auto",
        "compile_origin": "auto",
        "update_knowledge": "auto",
    },
}

ACTION_TYPE_MAP = {
    "seo_meta_fix": "seo_fix",
    "pixel_css_fix": "css_fix",
    "inject_css": "css_fix",
    "compile_origin": "auto",
    "update_knowledge": "knowledge_sync",
    "queue_outreach": "lead_outreach",
    "send_reminder": "invoice_reminder",
}


async def get_tenant_settings(tenant_id: str) -> dict:
    """Get approval settings for tenant, or defaults."""
    db = _get_db()
    if db is not None:
        settings = await db.approval_settings.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )
        if settings:
            merged = {**DEFAULT_SETTINGS, **settings}
            merged["rules"] = {**DEFAULT_SETTINGS["rules"], **settings.get("rules", {})}
            return merged
    return {**DEFAULT_SETTINGS, "tenant_id": tenant_id}


async def update_tenant_settings(tenant_id: str, updates: dict) -> dict:
    """Update approval settings for a tenant."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}

    updates["tenant_id"] = tenant_id
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.approval_settings.update_one(
        {"tenant_id": tenant_id},
        {"$set": updates},
        upsert=True,
    )
    return await get_tenant_settings(tenant_id)


# ═══════════════════════════════════════
# CORE EVALUATION
# ═══════════════════════════════════════

async def evaluate(action: dict, tenant_id: str, context: dict = None) -> dict:
    """
    Evaluate a single action and return approval decision.

    Returns:
        {
            "decision": "auto" | "auto_cancel" | "manual" | "blocked",
            "reason": str,
            "countdown_minutes": int (if auto_cancel),
            "confidence": float (if pattern-learned),
        }
    """
    settings = await get_tenant_settings(tenant_id)
    strategy = action.get("strategy", "")
    severity = action.get("severity", "P3")

    # Map strategy to action type
    action_type = ACTION_TYPE_MAP.get(strategy, strategy)
    rule = settings["rules"].get(action_type, "manual")

    # P0 severity always manual
    if severity == "P0":
        return _queue_manual(action, tenant_id, settings, "P0 severity requires manual approval")

    # Always-auto types
    if rule == "auto":
        return {"decision": "auto", "reason": f"{action_type} is always auto-approved"}

    # Auto with logging
    if rule == "auto_log":
        return {"decision": "auto", "reason": f"{action_type} auto with logging (draft, not sent)"}

    # Conditional rules
    if rule == "conditional":
        return await _evaluate_conditional(action, action_type, tenant_id, settings, context)

    # Manual required
    if rule == "manual":
        return _queue_manual(action, tenant_id, settings, f"{action_type} requires manual approval")

    # Blocked
    if rule == "blocked":
        return {"decision": "blocked", "reason": f"{action_type} is blocked"}

    # Default: check pattern learning
    return await _check_pattern_learning(action, action_type, tenant_id, settings)


async def _evaluate_conditional(action: dict, action_type: str, tenant_id: str,
                                 settings: dict, context: dict = None) -> dict:
    """Evaluate conditional rules based on thresholds and time."""
    finding = action.get("finding_type", "")

    # Invoice reminder: check amount threshold
    if action_type == "invoice_reminder":
        amount = action.get("amount", 0)
        if not amount and context:
            amount = context.get("invoice_amount", 0)
        limit = settings.get("invoice_auto_limit", 500)
        if amount <= limit:
            return {"decision": "auto", "reason": f"Invoice ${amount} <= ${limit} threshold"}
        return _queue_manual(action, tenant_id, settings, f"Invoice ${amount} > ${limit} threshold")

    # Lead outreach: check score and hours
    if action_type == "lead_outreach":
        score = action.get("lead_score", 0)
        if not score and context:
            score = context.get("lead_score", 0)
        vip_threshold = settings.get("vip_threshold", 85)

        if score >= vip_threshold:
            return _queue_manual(action, tenant_id, settings, f"VIP lead (score {score} >= {vip_threshold})")

        hours = settings.get("auto_approve_hours", [9, 18])
        current_hour = datetime.now(timezone.utc).hour
        if hours[0] <= current_hour < hours[1]:
            return {"decision": "auto", "reason": f"Lead score {score}, within business hours"}
        return {
            "decision": "auto_cancel",
            "reason": f"Lead score {score}, outside hours — queued for morning",
            "countdown_minutes": _minutes_until_hour(hours[0]),
            "confidence": 0.85,
        }

    # Bulk outreach: check count
    if action_type == "bulk_outreach":
        count = action.get("count", 0)
        if not count and context:
            count = context.get("outreach_count", 0)
        limit = settings.get("bulk_outreach_limit", 10)
        if count <= limit:
            return {"decision": "auto", "reason": f"Bulk outreach {count} <= {limit} limit"}
        return _queue_manual(action, tenant_id, settings, f"Bulk outreach {count} > {limit} limit")

    # Fallback: check pattern learning
    return await _check_pattern_learning(action, action_type, tenant_id, settings)


def _minutes_until_hour(target_hour: int) -> int:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return int((target - now).total_seconds() / 60)


def _queue_manual(action: dict, tenant_id: str, settings: dict, reason: str) -> dict:
    """Build a manual approval decision."""
    action_type = ACTION_TYPE_MAP.get(action.get("strategy", ""), action.get("strategy", "unknown"))
    return {
        "decision": "manual",
        "reason": reason,
        "whatsapp_message": _format_whatsapp_manual(action, action_type),
    }


# ═══════════════════════════════════════
# PATTERN LEARNING
# ═══════════════════════════════════════

async def _check_pattern_learning(action: dict, action_type: str, tenant_id: str, settings: dict) -> dict:
    """Check if we have enough pattern data to auto-decide."""
    if not settings.get("pattern_learning_enabled", True):
        return {"decision": "manual", "reason": "Pattern learning disabled"}

    db = _get_db()
    if db is None:
        return {"decision": "manual", "reason": "DB unavailable for pattern check"}

    threshold = settings.get("pattern_threshold", 20)
    patterns = await db.approval_patterns.find(
        {"tenant_id": tenant_id, "action_type": action_type}
    ).to_list(200)

    if len(patterns) < threshold:
        remaining = threshold - len(patterns)
        return {
            "decision": "manual",
            "reason": f"Learning: {len(patterns)}/{threshold} decisions recorded ({remaining} more needed)",
            "pattern_progress": len(patterns) / threshold,
        }

    yes_count = sum(1 for p in patterns if p.get("decision") == "YES")
    yes_rate = yes_count / len(patterns) if patterns else 0

    if yes_rate > 0.90:
        return {
            "decision": "auto",
            "reason": f"Pattern learned: {yes_rate:.0%} approval rate ({len(patterns)} decisions)",
            "confidence": yes_rate,
        }
    elif yes_rate >= 0.70:
        return {
            "decision": "auto_cancel",
            "reason": f"Pattern: {yes_rate:.0%} rate — auto in 15min, reply STOP to cancel",
            "countdown_minutes": 15,
            "confidence": yes_rate,
        }
    else:
        return {
            "decision": "manual",
            "reason": f"Pattern: {yes_rate:.0%} rate too low for auto-approve",
            "confidence": yes_rate,
        }


async def record_pattern(tenant_id: str, action_type: str, decision: str,
                          context: dict = None, response_time_minutes: float = None):
    """Record an approval decision for pattern learning."""
    db = _get_db()
    if db is None:
        return

    now = datetime.now(timezone.utc)
    await db.approval_patterns.insert_one({
        "tenant_id": tenant_id,
        "action_type": action_type,
        "decision": decision,
        "hour_of_day": now.hour,
        "day_of_week": now.strftime("%A"),
        "response_time_minutes": response_time_minutes,
        "context": context or {},
        "created_at": now.isoformat(),
    })


async def get_pattern_stats(tenant_id: str = None) -> dict:
    """Get pattern learning stats for a tenant (or all if None)."""
    db = _get_db()
    if db is None:
        return {"total": 0, "action_types": {}}

    settings = await get_tenant_settings(tenant_id or "default")
    threshold = settings.get("pattern_threshold", 20)

    query = {"tenant_id": tenant_id} if tenant_id else {}
    patterns = await db.approval_patterns.find(
        query, {"_id": 0}
    ).to_list(2000)

    by_type = {}
    for p in patterns:
        at = p.get("action_type", "unknown")
        if at not in by_type:
            by_type[at] = {"total": 0, "yes": 0, "no": 0}
        by_type[at]["total"] += 1
        if p.get("decision") == "YES":
            by_type[at]["yes"] += 1
        else:
            by_type[at]["no"] += 1

    action_stats = {}
    fully_automated = 0
    for at, counts in by_type.items():
        yes_rate = counts["yes"] / counts["total"] if counts["total"] > 0 else 0
        automated = counts["total"] >= threshold and yes_rate > 0.90
        if automated:
            fully_automated += 1
        action_stats[at] = {
            "total_decisions": counts["total"],
            "yes_rate": round(yes_rate * 100, 1),
            "remaining": max(0, threshold - counts["total"]),
            "automated": automated,
        }

    return {
        "total_decisions": len(patterns),
        "action_types": action_stats,
        "fully_automated": fully_automated,
        "threshold": threshold,
    }


# ═══════════════════════════════════════
# APPROVAL QUEUE MANAGEMENT
# ═══════════════════════════════════════

async def create_approval(tenant_id: str, action: dict, decision_info: dict,
                           run_id: str = None) -> dict:
    """Create a pending approval in the queue."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}

    approval_id = str(uuid.uuid4())[:12]
    now = datetime.now(timezone.utc)

    entry = {
        "approval_id": approval_id,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "action": action,
        "action_type": ACTION_TYPE_MAP.get(action.get("strategy", ""), action.get("strategy", "unknown")),
        "decision_type": decision_info.get("decision", "manual"),
        "reason": decision_info.get("reason", ""),
        "status": "pending",
        "created_at": now.isoformat(),
    }

    if decision_info.get("decision") == "auto_cancel":
        countdown = decision_info.get("countdown_minutes", 15)
        entry["auto_execute_at"] = (now + timedelta(minutes=countdown)).isoformat()
        entry["countdown_minutes"] = countdown
        entry["confidence"] = decision_info.get("confidence", 0)

    if decision_info.get("whatsapp_message"):
        entry["whatsapp_message"] = decision_info["whatsapp_message"]

    await db.approval_queue.insert_one(entry)

    return {k: v for k, v in entry.items() if k != "_id"}


async def get_pending_approvals(tenant_id: str = None) -> list:
    """Get all pending approvals, optionally filtered by tenant."""
    db = _get_db()
    if db is None:
        return []

    query = {"status": "pending"}
    if tenant_id:
        query["tenant_id"] = tenant_id

    approvals = await db.approval_queue.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Check auto-cancel countdowns
    now = datetime.now(timezone.utc)
    for a in approvals:
        if a.get("auto_execute_at"):
            exec_time = datetime.fromisoformat(a["auto_execute_at"])
            remaining = (exec_time - now).total_seconds() / 60
            a["countdown_remaining_minutes"] = max(0, round(remaining, 1))

    return approvals


async def process_approval(approval_id: str, decision: str, reason: str = "",
                            decided_by: str = "admin") -> dict:
    """Process a single approval (approve or reject)."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}

    approval = await db.approval_queue.find_one(
        {"approval_id": approval_id}, {"_id": 0}
    )
    if not approval:
        return {"error": "Approval not found"}

    if approval.get("status") != "pending":
        return {"error": f"Approval already {approval.get('status')}"}

    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(approval["created_at"])
    response_minutes = (now - created).total_seconds() / 60

    await db.approval_queue.update_one(
        {"approval_id": approval_id},
        {"$set": {
            "status": "approved" if decision == "approve" else "rejected",
            "decided_by": decided_by,
            "decided_at": now.isoformat(),
            "rejection_reason": reason if decision == "reject" else None,
            "response_time_minutes": round(response_minutes, 1),
        }}
    )

    # Record pattern
    await record_pattern(
        tenant_id=approval.get("tenant_id", ""),
        action_type=approval.get("action_type", ""),
        decision="YES" if decision == "approve" else "NO",
        context={"severity": approval.get("action", {}).get("severity")},
        response_time_minutes=response_minutes,
    )

    return {
        "approval_id": approval_id,
        "status": "approved" if decision == "approve" else "rejected",
        "action_type": approval.get("action_type"),
        "response_time_minutes": round(response_minutes, 1),
    }


async def get_approval_history(tenant_id: str = None, limit: int = 50) -> list:
    """Get approval decision history."""
    db = _get_db()
    if db is None:
        return []

    query = {"status": {"$in": ["approved", "rejected", "auto_approved", "auto_cancel_approved"]}}
    if tenant_id:
        query["tenant_id"] = tenant_id

    history = await db.approval_queue.find(
        query, {"_id": 0}
    ).sort("decided_at", -1).to_list(limit)

    return history


async def get_approval_stats(tenant_id: str = None) -> dict:
    """Get approval statistics."""
    db = _get_db()
    if db is None:
        return {}

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    base_q = {"tenant_id": tenant_id} if tenant_id else {}

    pending = await db.approval_queue.count_documents({**base_q, "status": "pending"})
    auto_today = await db.approval_queue.count_documents({
        **base_q,
        "status": {"$in": ["auto_approved", "auto_cancel_approved"]},
        "decided_at": {"$gte": today_start},
    })
    manual_today = await db.approval_queue.count_documents({
        **base_q,
        "status": {"$in": ["approved", "rejected"]},
        "decided_at": {"$gte": today_start},
    })

    total = await db.approval_queue.count_documents(base_q)
    auto_total = await db.approval_queue.count_documents({
        **base_q, "status": {"$in": ["auto_approved", "auto_cancel_approved"]}
    })
    auto_rate = round((auto_total / total * 100) if total > 0 else 0, 1)

    pattern_stats = await get_pattern_stats(tenant_id) if tenant_id else {"total_decisions": 0, "fully_automated": 0}

    return {
        "pending": pending,
        "auto_approved_today": auto_today,
        "manual_today": manual_today,
        "total": total,
        "automation_rate": auto_rate,
        "pattern_stats": pattern_stats,
    }


# ═══════════════════════════════════════
# WHATSAPP MESSAGE FORMATTING
# ═══════════════════════════════════════

def _format_whatsapp_manual(action: dict, action_type: str) -> str:
    strategy = action.get("strategy", action_type)
    severity = action.get("severity", "P2")
    return (
        f"ORA needs approval:\n"
        f"Action: {strategy}\n"
        f"Detail: {action.get('finding_type', 'system action')}\n"
        f"Risk: {severity}\n"
        f"Reply YES {{action_id}} or NO {{action_id}}"
    )


def format_whatsapp_auto_cancel(action: dict, action_type: str,
                                  approval_id: str, countdown: int, confidence: float) -> str:
    strategy = action.get("strategy", action_type)
    return (
        f"ORA: {strategy}\n"
        f"Confidence: {confidence:.0%} based on your history.\n"
        f"Auto-proceeds in {countdown} min.\n"
        f"Reply STOP {approval_id} to cancel."
    )


def parse_whatsapp_reply(message: str) -> dict:
    """Parse incoming WhatsApp approval replies."""
    msg = message.strip().upper()

    if msg.startswith("YES "):
        return {"command": "approve", "action_id": msg[4:].strip()}
    elif msg.startswith("NO "):
        return {"command": "reject", "action_id": msg[3:].strip()}
    elif msg.startswith("STOP ALL"):
        return {"command": "stop_all"}
    elif msg.startswith("STOP "):
        return {"command": "cancel", "action_id": msg[5:].strip()}
    else:
        return {"command": "unknown", "raw": message}


# ═══════════════════════════════════════
# PIPELINE INTEGRATION — Stage 5 Entry Point
# ═══════════════════════════════════════

async def process_pipeline_actions(tenant_id: str, actions: dict, run_id: str = None) -> dict:
    """
    Process all pipeline actions through the Smart Approval engine.
    Called by flow_coordinator Stage 5.

    Non-blocking: auto-approved actions proceed immediately.
    Manual actions are queued — pipeline logs them but doesn't block.
    """
    approved = []
    queued = []
    auto_count = 0
    manual_count = 0

    for action in actions.get("actions", []):
        decision = await evaluate(action, tenant_id, context=action)

        if decision["decision"] == "auto":
            action["approval_status"] = "auto_approved"
            action["approval_reason"] = decision["reason"]
            approved.append(action)
            auto_count += 1

            # Log auto-approval
            db = _get_db()
            if db is not None:
                await db.approval_queue.insert_one({
                    "approval_id": str(uuid.uuid4())[:12],
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "action": action,
                    "action_type": ACTION_TYPE_MAP.get(action.get("strategy", ""), action.get("strategy", "")),
                    "decision_type": "auto",
                    "reason": decision["reason"],
                    "status": "auto_approved",
                    "decided_at": datetime.now(timezone.utc).isoformat(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        elif decision["decision"] == "auto_cancel":
            action["approval_status"] = "auto_cancel_pending"
            action["approval_reason"] = decision["reason"]
            action["countdown_minutes"] = decision.get("countdown_minutes", 15)
            approval = await create_approval(tenant_id, action, decision, run_id)
            action["approval_id"] = approval.get("approval_id")
            approved.append(action)
            auto_count += 1

        elif decision["decision"] == "manual":
            action["approval_status"] = "pending_manual"
            action["approval_reason"] = decision["reason"]
            approval = await create_approval(tenant_id, action, decision, run_id)
            action["approval_id"] = approval.get("approval_id")
            queued.append(action)
            manual_count += 1

            # Send WhatsApp notification (non-blocking)
            try:
                from services.twilio_service import send_whatsapp_message
                msg = decision.get("whatsapp_message", _format_whatsapp_manual(action, action.get("strategy", "")))
                msg = msg.replace("{action_id}", approval.get("approval_id", ""))
                await send_whatsapp_message(
                    os.environ.get("ADMIN_ALERT_PHONE", os.environ.get("FOUNDER_PHONE", "")), msg)
            except Exception:
                pass

        elif decision["decision"] == "blocked":
            action["approval_status"] = "blocked"
            action["approval_reason"] = decision["reason"]
            queued.append(action)
            manual_count += 1

    return {
        "tenant_id": tenant_id,
        "approved": approved,
        "pending": queued,
        "all_approved": len(queued) == 0,
        "auto_count": auto_count,
        "manual_count": manual_count,
        "summary": f"{auto_count} auto-approved, {manual_count} queued for review",
    }
