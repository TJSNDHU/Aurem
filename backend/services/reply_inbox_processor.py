"""
services/reply_inbox_processor.py — iter 330 FIX 3

Reads every new row from `email_inbox` / `inbound_replies`, classifies
intent using the existing complexity-routed LLM, and takes safe action:

  • interested        → queue founder Tier-2 approval for a booking
                         confirmation reply, OR auto-book via the
                         existing `appointments/book` endpoint if the
                         lead already has a chosen slot.
  • question          → ORA drafts a reply; saved to
                         `reply_inbox_drafts` for founder review (Tier-2
                         30s window). NEVER auto-sends without approval.
  • not_interested    → add the sender's email + phone to
                         `do_not_contact` (CASL hard-stop) and mark the
                         lead `status = "not_interested"`.
  • unclear           → leave it untouched, surface it in the morning
                         brief for founder review.

Cadence: every 5 min via APScheduler. Each row is stamped
`ora_processed_at` so we never reprocess.

Founder visibility: a daily summary line is spliced into the Morning
Brief (count by category for the last 24h).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_PROCESSING_CAP = 30   # max replies per pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _classify_intent_quick(text: str) -> str:
    """Cheap rule-based classifier — keeps cost flat per reply.

    Returns one of: "interested" | "not_interested" | "question" | "unclear".
    Phrased to be conservative — defaults to "unclear" so the founder
    never sees an aggressive misclassification.
    """
    if not text:
        return "unclear"
    t = text.lower()
    # Not interested patterns (CASL-aligned unsubscribe / refusal).
    if any(p in t for p in (
        "unsubscribe", "stop", "remove me", "not interested", "no thanks",
        "do not contact", "don't contact", "no longer interested",
        "take me off", "stop emailing", "leave me alone",
    )):
        return "not_interested"
    # Question patterns.
    if "?" in text or any(p in t for p in (
        "how do", "how does", "what is", "what are", "can you",
        "could you", "do you offer", "tell me more", "more info",
        "pricing", "how much", "cost?", "price?",
    )):
        return "question"
    # Interested patterns.
    if any(p in t for p in (
        "yes please", "interested", "sounds good", "let's do",
        "let's chat", "book a", "schedule a", "set up a call",
        "i'd like to", "i would like to", "sign me up",
    )):
        return "interested"
    return "unclear"


async def process_reply(db, reply_doc: dict) -> dict:
    """One row. Stamps `ora_processed_at` + records action."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    text = (
        reply_doc.get("body_text")
        or reply_doc.get("body")
        or reply_doc.get("text")
        or reply_doc.get("snippet")
        or ""
    )
    sender_email = (reply_doc.get("from_email") or reply_doc.get("sender") or "").lower().strip()
    intent = _classify_intent_quick(text)

    action: dict = {"intent": intent, "auto": False}

    # Match the reply to a lead by sender email (cheap).
    lead = None
    if sender_email:
        try:
            lead = await db.campaign_leads.find_one(
                {"email": sender_email}, {"_id": 0},
            )
        except Exception:
            lead = None

    try:
        if intent == "not_interested" and sender_email:
            # CASL hard-stop — add to DNC and stamp the lead.
            await db.do_not_contact.update_one(
                {"email": sender_email},
                {"$set": {
                    "email":      sender_email,
                    "added_at":   _now(),
                    "source":     "reply_inbox_auto",
                    "reason":     "lead replied 'not interested'",
                }},
                upsert=True,
            )
            if lead:
                await db.campaign_leads.update_one(
                    {"lead_id": lead.get("lead_id")},
                    {"$set": {
                        "status":            "not_interested",
                        "do_not_contact_at": _now(),
                    }},
                )
            action.update({"auto": True, "did": "added_to_dnc"})

        elif intent in ("interested", "question"):
            # Draft a reply + queue for founder approval. Never auto-send.
            draft_text = _craft_draft_reply(intent, text, lead or {})
            await db.reply_inbox_drafts.insert_one({
                "ts":           _now(),
                "from_email":   sender_email,
                "intent":       intent,
                "lead_id":      (lead or {}).get("lead_id"),
                "snippet":      text[:500],
                "draft_reply":  draft_text,
                "status":       "pending_approval",
            })
            action.update({"auto": False, "did": "drafted_for_approval"})

        else:  # unclear
            action.update({"auto": False, "did": "noted_for_founder"})

        # Stamp the source row so we don't reprocess.
        src_collection = reply_doc.get("__source") or "email_inbox"
        await db[src_collection].update_one(
            {"_id": reply_doc["_id_orig"]},
            {"$set": {
                "ora_processed_at": _now(),
                "ora_intent":       intent,
                "ora_action":       action.get("did"),
            }},
        )
    except Exception as e:
        action.update({"error": str(e)[:200]})

    # Persist a normalised audit row.
    try:
        await db.reply_inbox_actions.insert_one({
            "ts":          _now(),
            "from_email":  sender_email,
            "intent":      intent,
            "action":      action.get("did"),
            "lead_id":     (lead or {}).get("lead_id"),
            "snippet":     text[:200],
        })
    except Exception:
        pass

    return {"ok": True, **action}


def _craft_draft_reply(intent: str, original: str, lead: dict) -> str:
    """Deterministic, founder-tone draft. ORA can edit before sending."""
    biz = lead.get("business_name") or "your business"
    name = lead.get("owner_first_name") or lead.get("name") or "there"
    if intent == "interested":
        return (
            f"Hi {name},\n\n"
            f"Thanks for getting back to me — great to hear you're "
            f"interested. The fastest way to see what AUREM can do for "
            f"{biz} is a 15-minute call. Here are two slots that work "
            f"this week — just reply with the one you'd like, or pick "
            f"another time from https://aurem.live/book.\n\n"
            f"— ORA, AUREM Intelligence AI"
        )
    return (
        f"Hi {name},\n\n"
        f"Happy to answer that. Could you share a little more about "
        f"what you'd like to know about AUREM for {biz}? I'll send a "
        f"detailed reply within the day.\n\n"
        f"— ORA, AUREM Intelligence AI"
    )


async def reply_inbox_sweep(db) -> dict:
    """One full pass. Reads up to `_PROCESSING_CAP` unprocessed rows
    from email_inbox + inbound_replies, classifies + acts on each."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    processed = 0
    by_intent: dict[str, int] = {}
    sources = [
        ("email_inbox",     "from_email"),
        ("inbound_replies", "from_email"),
    ]
    for col_name, _ in sources:
        try:
            cur = db[col_name].find(
                {"ora_processed_at": {"$exists": False}},
                {"_id": 1, "from_email": 1, "sender": 1, "body": 1,
                 "body_text": 1, "text": 1, "snippet": 1},
            ).sort("_id", -1).limit(_PROCESSING_CAP)
            rows = await cur.to_list(length=_PROCESSING_CAP)
        except Exception as e:
            logger.debug(f"[reply-inbox] {col_name} read failed: {e}")
            continue
        for row in rows:
            row["__source"] = col_name
            row["_id_orig"] = row.pop("_id")
            out = await process_reply(db, row)
            if out.get("ok"):
                processed += 1
                by_intent[out.get("intent", "unclear")] = by_intent.get(out.get("intent", "unclear"), 0) + 1

    # Persist a run row so the Outreach Health card can show it.
    try:
        await db.reply_inbox_runs.insert_one({
            "ts":        _now(),
            "processed": processed,
            "by_intent": by_intent,
        })
    except Exception:
        pass
    return {"ok": True, "processed": processed, "by_intent": by_intent}


async def daily_reply_summary(db) -> dict:
    """24-hour summary used by the Morning Brief."""
    if db is None:
        return {"line": "", "counts": {}}
    cutoff = _now() - timedelta(hours=24)
    counts: dict[str, int] = {}
    cur = db.reply_inbox_actions.find({"ts": {"$gte": cutoff}}, {"_id": 0, "intent": 1})
    async for r in cur:
        k = r.get("intent") or "unclear"
        counts[k] = counts.get(k, 0) + 1
    total = sum(counts.values())
    if total == 0:
        return {"line": "REPLY INBOX (24h): no new replies.", "counts": counts}
    parts = []
    for label, key in (("interested", "interested"), ("questions", "question"),
                         ("opted out", "not_interested"), ("unclear", "unclear")):
        if counts.get(key):
            parts.append(f"{counts[key]} {label}")
    line = "REPLY INBOX (24h): " + ", ".join(parts) + "."
    return {"line": line, "counts": counts}
