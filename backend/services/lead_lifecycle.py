"""
Lead Lifecycle Service
----------------------
State machine for AUREM prospects — ensures zero leads are ever lost.

Stages (linear + branching):
  new → contacted → engaged → called_no_response → following_up → won
                                                                → cold (after 60d no response)
                                                                     → re-approach (every 90d)

The service records touchpoints, schedules drip actions, and gates
transitions so lifecycle events cannot happen out-of-order.

Public API:
  await transition(db, lead_id, new_stage, reason=...) -> dict
  await record_touchpoint(db, lead_id, channel, kind, status, details=...) -> None
  await get_pipeline_board(db) -> dict  # grouped by stage for Kanban UI
  await get_metrics(db) -> dict
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Canonical stage order
STAGES = ["new", "contacted", "engaged", "called_no_response", "following_up", "won", "cold"]
ACTIVE_STAGES = ["new", "contacted", "engaged", "called_no_response", "following_up"]
TERMINAL_STAGES = ["won", "cold"]

# Valid transitions (source → allowed targets). Any → won is always allowed (paid).
ALLOWED: dict[str, list[str]] = {
    "new":                  ["contacted", "engaged", "called_no_response", "won", "cold"],
    "contacted":            ["engaged", "called_no_response", "following_up", "won", "cold"],
    "engaged":              ["called_no_response", "following_up", "contacted", "won", "cold"],
    "called_no_response":   ["following_up", "engaged", "won", "cold"],
    "following_up":         ["engaged", "called_no_response", "won", "cold"],
    "won":                  [],  # terminal
    "cold":                 ["contacted", "following_up", "won"],  # re-approach possible
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def infer_stage(lead: dict) -> str:
    """Derive a lifecycle_stage from existing lead signals.

    Used both for (a) unstaged legacy leads so they appear in the right Kanban
    column, and (b) the one-time startup migration that backfills the field
    so drag-and-drop / metrics / transitions all work correctly.

    Priority order — first match wins:
      1. Terminal states: explicit status or flags
      2. Engaged  — lead replied / clicked / opened at least once
      3. Called   — call logged but no response
      4. Following up — follow-up scheduled / last_blast_at recent
      5. Contacted — any outbound attempt (wa/email/sms/touchpoint)
      6. Cold     — DNC or stale lead (>60d no activity)
      7. New      — default
    """
    if not isinstance(lead, dict):
        return "new"

    # 1. Terminal
    status = (lead.get("status") or "").lower()
    if status in ("won", "paid", "closed_won", "converted"):
        return "won"
    if status in ("do_not_contact", "dnc", "unsubscribed", "dead", "lost", "closed_lost"):
        return "cold"
    if lead.get("dnc") is True or lead.get("do_not_contact") is True:
        return "cold"

    # 2. Engaged — reply / open / click evidence
    if lead.get("replied_at") or lead.get("last_reply_at") or status in ("replied", "engaged", "responded"):
        return "engaged"
    if lead.get("clicked_at") or lead.get("link_clicked"):
        return "engaged"
    if status == "opened" or lead.get("opened_at"):
        return "engaged"
    if (lead.get("report_view_count") or 0) > 0 or (lead.get("sample_view_count") or 0) > 0:
        return "engaged"

    # 3. Called — call attempted without pickup
    if status in ("called_no_response", "no_answer", "voicemail"):
        return "called_no_response"
    if lead.get("last_call_status") in ("no_answer", "voicemail", "failed"):
        return "called_no_response"

    # 4. Following up
    if status in ("following_up", "follow_up", "reaching_out"):
        return "following_up"
    if lead.get("next_action_at") or lead.get("follow_up_scheduled_at"):
        return "following_up"
    # Recently re-blasted but no reply
    last_blast = lead.get("last_blast_at") or lead.get("last_blasted_at")
    if last_blast:
        try:
            dt = datetime.fromisoformat(str(last_blast).replace("Z", "+00:00"))
            if (_now() - dt) < timedelta(days=7) and ((lead.get("blast_count") or 0) > 1):
                return "following_up"
        except Exception:
            pass

    # 5. Contacted — any outbound attempt
    if status in ("contacted", "whatsapp_sent", "email_sent", "sms_sent", "blasted"):
        return "contacted"
    if lead.get("whatsapp_sent") or lead.get("email_sent") or lead.get("sms_sent"):
        return "contacted"
    if lead.get("whatsapp_sent_at") or lead.get("email_sent_at") or lead.get("contacted_at"):
        return "contacted"
    tps = lead.get("touchpoints")
    if tps and isinstance(tps, list) and len(tps) > 0:
        return "contacted"
    if (lead.get("outreach_history") and isinstance(lead.get("outreach_history"), list)
            and len(lead.get("outreach_history", [])) > 0):
        return "contacted"

    # 6. Cold by staleness — created >60d ago with no outreach
    created = lead.get("created_at") or lead.get("last_scouted_at")
    if created:
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            if (_now() - dt) > timedelta(days=60):
                return "cold"
        except Exception:
            pass

    # 7. Default
    return "new"


async def backfill_lifecycle_stages(db, dry_run: bool = False) -> dict:
    """One-time migration — set lifecycle_stage on every lead using infer_stage().
    Idempotent: only touches leads where field is missing or empty.
    Returns counts per stage assigned.
    """
    q = {"$or": [{"lifecycle_stage": {"$exists": False}}, {"lifecycle_stage": None}, {"lifecycle_stage": ""}]}
    now_iso = _iso(_now())
    counts: dict[str, int] = {s: 0 for s in STAGES}
    scanned = 0
    updated = 0
    cursor = db.campaign_leads.find({**q, "business_id": FOUNDER_BIN}, {"_id": 0})
    async for lead in cursor:
        scanned += 1
        stage = infer_stage(lead)
        if stage not in STAGES:
            stage = "new"
        counts[stage] += 1
        if dry_run:
            continue
        await db.campaign_leads.update_one(
            {"lead_id": lead.get("lead_id"), "business_id": FOUNDER_BIN},
            {"$set": {
                "lifecycle_stage": stage,
                "lifecycle_stage_changed_at": now_iso,
                "lifecycle_backfilled": True,
            }},
        )
        updated += 1
    return {"scanned": scanned, "updated": updated, "counts": counts, "dry_run": dry_run}


# ─────────────────────────────────────────────────────────────
# Transitions
# ─────────────────────────────────────────────────────────────
async def transition(
    db,
    lead_id: str,
    new_stage: str,
    reason: str = "",
    by: str = "system",
    force: bool = False,
) -> dict:
    """Move a lead to a new stage. Returns {ok, from, to, skipped?}."""
    if new_stage not in STAGES:
        return {"ok": False, "error": f"unknown stage: {new_stage}"}

    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"_id": 0, "lifecycle_stage": 1})
    if not lead:
        return {"ok": False, "error": "lead_not_found"}

    current = lead.get("lifecycle_stage") or "new"
    if current == new_stage:
        return {"ok": True, "from": current, "to": new_stage, "skipped": "already_in_stage"}

    allowed = ALLOWED.get(current, [])
    if not force and new_stage not in allowed and new_stage != "won":
        return {"ok": False, "error": f"transition not allowed: {current} → {new_stage}"}

    now = _now()
    history_entry = {
        "from": current,
        "to": new_stage,
        "at": _iso(now),
        "reason": reason or "",
        "by": by,
    }

    update: dict[str, Any] = {
        "lifecycle_stage": new_stage,
        "lifecycle_stage_changed_at": _iso(now),
    }
    # If moving to won or cold → stop drip; if moving to called_no_response → start drip
    if new_stage == "won":
        update["drip.completed"] = True
        update["drip.next_action_at"] = None
    elif new_stage == "called_no_response":
        # Start a fresh drip — scheduler picks up next_action_at
        update["drip.started_at"] = _iso(now)
        update["drip.completed"] = False
        update["drip.steps_completed"] = []
        update["drip.next_step_day"] = 1
        update["drip.next_action_at"] = _iso(now + timedelta(days=1))
    elif new_stage == "cold":
        # Cold lead: re-approach in 90 days
        update["drip.completed"] = True
        update["drip.next_action_at"] = _iso(now + timedelta(days=90))
    elif new_stage == "following_up":
        # Keep next_action_at driven by drip scheduler; no change here

        pass

    await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {
            "$set": update,
            "$push": {"lifecycle_history": history_entry},
        },
    )
    logger.info(f"[Lifecycle] {lead_id}: {current} → {new_stage} ({reason})")
    return {"ok": True, "from": current, "to": new_stage, "at": _iso(now)}


# ─────────────────────────────────────────────────────────────
# Touchpoint logging
# ─────────────────────────────────────────────────────────────
async def record_touchpoint(
    db,
    lead_id: str,
    channel: str,
    kind: str,
    status: str,
    details: Optional[dict] = None,
) -> None:
    """Append a touchpoint entry to the lead's history."""
    entry = {
        "channel": channel,        # email | whatsapp | sms | call
        "kind": kind,              # drip_day1 | flame_auto_dial | scout | manual_blast | ...
        "status": status,          # sent | failed | opened | answered | voicemail | read
        "at": _iso(_now()),
        "details": details or {},
    }
    try:
        await db.campaign_leads.update_one(
            {"lead_id": lead_id, "business_id": FOUNDER_BIN},
            {"$push": {"touchpoints": {"$each": [entry], "$slice": -200}}},  # keep last 200
        )
    except Exception as e:
        logger.warning(f"[Lifecycle] touchpoint log failed {lead_id}: {e}")


# ─────────────────────────────────────────────────────────────
# Manual: note, next-action override
# ─────────────────────────────────────────────────────────────
async def add_note(db, lead_id: str, note: str, by: str = "admin") -> dict:
    if not note or not note.strip():
        return {"ok": False, "error": "empty_note"}
    await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"$push": {"notes_log": {"note": note.strip(), "by": by, "at": _iso(_now())}}},
    )
    return {"ok": True}


async def set_next_action(db, lead_id: str, when_iso: str, action_type: str = "manual") -> dict:
    await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"$set": {"drip.next_action_at": when_iso, "drip.next_action_type_override": action_type}},
    )
    return {"ok": True, "next_action_at": when_iso}


# ─────────────────────────────────────────────────────────────
# Pipeline board for Kanban
# ─────────────────────────────────────────────────────────────
async def get_pipeline_board(db, limit_per_stage: int = 50) -> dict:
    """Returns leads grouped by lifecycle_stage, newest first."""
    board: dict[str, list] = {s: [] for s in STAGES}
    counts: dict[str, int] = {s: 0 for s in STAGES}
    for stage in STAGES:
        cursor = db.campaign_leads.find(
            {"lifecycle_stage": stage, "business_id": FOUNDER_BIN},
            {
                "_id": 0, "lead_id": 1, "business_name": 1, "contact_name": 1,
                "phone": 1, "email": 1, "website_url": 1, "tenant_id": 1,
                "lifecycle_stage": 1, "lifecycle_stage_changed_at": 1,
                "drip": 1, "touchpoints": {"$slice": -5},
                "verification": 1, "dnc": 1, "flame_score": 1, "notes_log": {"$slice": -3},
            },
        ).sort("lifecycle_stage_changed_at", -1).limit(limit_per_stage)
        docs = await cursor.to_list(length=limit_per_stage)
        now = _now()
        for d in docs:
            try:
                changed = datetime.fromisoformat(str(d.get("lifecycle_stage_changed_at", "")).replace("Z", "+00:00"))
                days_in = int((now - changed).total_seconds() // 86400)
            except Exception:
                days_in = 0
            d["days_in_stage"] = days_in
            board[stage].append(d)
        # Total count (not just limited)
        counts[stage] = await db.campaign_leads.count_documents(
            {"lifecycle_stage": stage, "business_id": FOUNDER_BIN})

    # Unstaged (legacy leads without lifecycle_stage) → INFER stage per lead
    # and distribute across all columns (previously dumped everything into 'new').
    unstaged_q = {"business_id": FOUNDER_BIN, "$or": [
        {"lifecycle_stage": {"$exists": False}},
        {"lifecycle_stage": None},
        {"lifecycle_stage": ""},
    ]}
    unstaged_count = await db.campaign_leads.count_documents(unstaged_q)
    if unstaged_count > 0:
        cursor = db.campaign_leads.find(
            unstaged_q,  # carries business_id scope
            {
                "_id": 0, "lead_id": 1, "business_name": 1, "contact_name": 1,
                "phone": 1, "email": 1, "website_url": 1, "tenant_id": 1,
                "verification": 1, "dnc": 1, "do_not_contact": 1, "status": 1,
                "whatsapp_sent": 1, "email_sent": 1, "sms_sent": 1,
                "whatsapp_sent_at": 1, "email_sent_at": 1, "contacted_at": 1,
                "replied_at": 1, "last_reply_at": 1, "clicked_at": 1, "opened_at": 1,
                "report_view_count": 1, "sample_view_count": 1,
                "last_call_status": 1, "next_action_at": 1, "follow_up_scheduled_at": 1,
                "last_blast_at": 1, "last_blasted_at": 1, "blast_count": 1,
                "touchpoints": 1, "outreach_history": {"$slice": -5},
                "notes_log": {"$slice": -3},
                "flame_score": 1, "created_at": 1, "last_scouted_at": 1,
            },
        )
        per_stage_room = {s: max(0, limit_per_stage - len(board[s])) for s in STAGES}
        inferred_counts: dict[str, int] = {s: 0 for s in STAGES}
        async for d in cursor:
            stage = infer_stage(d)
            if stage not in STAGES:
                stage = "new"
            inferred_counts[stage] += 1
            if per_stage_room.get(stage, 0) > 0:
                d["lifecycle_stage"] = stage
                d["days_in_stage"] = 0
                d["_unstaged"] = True
                board[stage].append(d)
                per_stage_room[stage] -= 1
        for s in STAGES:
            counts[s] += inferred_counts[s]

    return {"board": board, "counts": counts, "stages": STAGES, "as_of": _iso(_now())}


# ─────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────
async def get_metrics(db) -> dict:
    """Conversion funnel + channel perf + pipeline value."""
    # Stage counts (distribute unstaged via infer_stage so metrics match Kanban)
    by_stage = {}
    for s in STAGES:
        by_stage[s] = await db.campaign_leads.count_documents(
            {"lifecycle_stage": s, "business_id": FOUNDER_BIN})
    unstaged_cursor = db.campaign_leads.find(
        {"business_id": FOUNDER_BIN, "$or": [
            {"lifecycle_stage": {"$exists": False}},
            {"lifecycle_stage": None},
            {"lifecycle_stage": ""},
        ]},
        {
            "_id": 0, "status": 1, "dnc": 1, "do_not_contact": 1,
            "whatsapp_sent": 1, "email_sent": 1, "sms_sent": 1,
            "whatsapp_sent_at": 1, "email_sent_at": 1, "contacted_at": 1,
            "replied_at": 1, "last_reply_at": 1, "clicked_at": 1, "opened_at": 1,
            "report_view_count": 1, "sample_view_count": 1,
            "last_call_status": 1, "next_action_at": 1, "follow_up_scheduled_at": 1,
            "last_blast_at": 1, "last_blasted_at": 1, "blast_count": 1,
            "touchpoints": 1, "outreach_history": 1,
            "created_at": 1, "last_scouted_at": 1,
        },
    )
    async for d in unstaged_cursor:
        s = infer_stage(d)
        if s in by_stage:
            by_stage[s] += 1
    total = sum(by_stage.values()) or 1

    # Conversion (funnel): successive stage pass-through
    def conv(num_stage: str, den_stage: str) -> float:
        d = by_stage.get(den_stage, 0)
        n = by_stage.get(num_stage, 0)
        return round((n / d) * 100, 1) if d else 0.0

    # Avg days to close (new → won)
    won_cursor = db.campaign_leads.find(
        {"lifecycle_stage": "won", "lifecycle_history": {"$exists": True},
         "business_id": FOUNDER_BIN},
        {"_id": 0, "lifecycle_history": 1},
    ).limit(200)
    durations = []
    async for doc in won_cursor:
        hist = doc.get("lifecycle_history") or []
        if not hist:
            continue
        try:
            first = datetime.fromisoformat(hist[0]["at"].replace("Z", "+00:00"))
            won_entry = next((h for h in hist if h.get("to") == "won"), None)
            if won_entry:
                last = datetime.fromisoformat(won_entry["at"].replace("Z", "+00:00"))
                durations.append((last - first).total_seconds() / 86400.0)
        except Exception:
            continue
    avg_days_to_close = round(sum(durations) / len(durations), 1) if durations else 0

    # Best channel — count touchpoints by channel with status=sent|answered|read
    try:
        agg = await db.campaign_leads.aggregate([
            {"$match": {"business_id": FOUNDER_BIN}},
            {"$unwind": "$touchpoints"},
            {"$group": {
                "_id": {"channel": "$touchpoints.channel", "status": "$touchpoints.status"},
                "count": {"$sum": 1},
            }},
        ]).to_list(length=200)
    except Exception:
        agg = []

    channel_perf: dict[str, dict] = {}
    for a in agg:
        key = (a["_id"] or {}).get("channel") or "unknown"
        status = (a["_id"] or {}).get("status") or "unknown"
        channel_perf.setdefault(key, {"sent": 0, "success": 0, "failed": 0})
        if status in ("sent", "initiated"):
            channel_perf[key]["sent"] += a["count"]
        elif status in ("answered", "read", "opened", "clicked"):
            channel_perf[key]["success"] += a["count"]
        elif status in ("failed", "undelivered"):
            channel_perf[key]["failed"] += a["count"]

    # Pipeline value: leads * assumed avg deal ($97/mo default)
    try:
        deal_value = float(__import__("os").environ.get("AUREM_AVG_DEAL_VALUE", "97"))
    except Exception:
        deal_value = 97.0
    active_leads = sum(by_stage.get(s, 0) for s in ACTIVE_STAGES)
    pipeline_value = round(active_leads * deal_value, 2)

    return {
        "total_leads": total,
        "by_stage": by_stage,
        "active_leads": active_leads,
        "pipeline_value": pipeline_value,
        "avg_deal_value": deal_value,
        "conversion": {
            "contacted_from_new": conv("contacted", "new") if by_stage.get("new") else 0,
            "engaged_from_contacted": conv("engaged", "contacted"),
            "called_from_engaged": conv("called_no_response", "engaged"),
            "won_from_followup": conv("won", "following_up"),
            "won_from_total": round((by_stage.get("won", 0) / total) * 100, 1),
        },
        "avg_days_to_close": avg_days_to_close,
        "channel_performance": channel_perf,
        "as_of": _iso(_now()),
    }
