"""
AUREM Blast Chain — Section 7 of growth-engine upgrade
======================================================
Replaces single-shot auto-blast with staggered 4-touch chains.

Two chains:
  • Chain A — for leads WITH a website (qa_has_website passed).
              Hooks into the existing website audit + report URL artifacts.
  • Chain B — for leads WITHOUT a website (qa_no_website passed).
              Hooks into the auto-built preview + 7-day claim CTA.

Cadence (default per spec): touch #1 → Day 0
                            touch #2 → Day 2
                            touch #3 → Day 5
                            touch #4 → Day 9
(Spaced as 0h, 48h, 120h, 216h from the initial fire.)

Reply handling:
  • Hot keywords (interested/pricing/yes/call me) → set hot_lead_flag,
    halt chain, fire Telegram alert.
  • DNC keywords (stop/unsubscribe/remove)        → add to do_not_contact,
    halt chain.

Persistence on `campaign_leads`:
  blast_chain: {
    id:          "chain_a" | "chain_b",
    started_at:  iso,
    touches:     [{n, sent_at, sent_count, results}],
    next_touch_n: 1..4,
    next_touch_at: iso (None when completed/halted),
    completed:    bool,
    halted_reason: "hot" | "dnc" | None,
  }
"""
from __future__ import annotations

import os
import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── tunables (env-overridable) ───────────────────────────────────────
CHAIN_SCHEDULE_DAYS: List[int] = [
    int(x) for x in os.environ.get("BLAST_CHAIN_DAYS", "0,2,5,9").split(",")
]
TOUCH_TIMEOUT_S = float(os.environ.get("BLAST_CHAIN_TOUCH_TIMEOUT_S", "30"))

# Hot / DNC keyword sets — case-insensitive whole-token regex matches
HOT_KEYWORDS = (
    "yes", "interested", "pricing", "price", "how much", "tell me more",
    "call me", "let's talk", "lets talk", "send info", "more info",
    "demo", "schedule", "book a call",
)
DNC_KEYWORDS = (
    "stop", "unsubscribe", "remove", "opt out", "opt-out", "do not contact",
    "no thanks", "not interested", "leave me alone", "fuck off", "f off",
)

_HOT_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in HOT_KEYWORDS) + r")\b", re.I,
)
_DNC_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in DNC_KEYWORDS) + r")\b", re.I,
)

# Per-touch tone variants — kept short on purpose; the existing
# render_blast_artifacts builds the bulk of the copy. We append a
# "touch hint" prefix to the subject + sms suffix to vary the chain.
_CHAIN_A_VARIANTS = {
    1: {"subject_prefix": "",                 "sms_suffix": ""},
    2: {"subject_prefix": "Re: ",             "sms_suffix": " (quick nudge)"},
    3: {"subject_prefix": "One more thought · ", "sms_suffix": " (last try this week)"},
    4: {"subject_prefix": "Closing your file · ", "sms_suffix": " (won't ping again unless you reply)"},
}
_CHAIN_B_VARIANTS = {
    1: {"subject_prefix": "",                  "sms_suffix": ""},
    2: {"subject_prefix": "Re: your free preview · ",     "sms_suffix": " (free preview live till expiry)"},
    3: {"subject_prefix": "Heads up · ",       "sms_suffix": " (preview link expires in 4 days)"},
    4: {"subject_prefix": "Final · ",          "sms_suffix": " (preview link goes dark soon)"},
}


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def assign_chain(lead: Dict[str, Any]) -> str:
    """Decide which chain a lead belongs to.

    Chain A → has-website (lead has any website url OR qa_checklist passed).
    Chain B → no-website  (no website + qa_no_website passed).
    Defaults to chain_a when ambiguous (matches old single-blast behaviour).
    """
    has_site = bool(
        (lead.get("website") or "").strip()
        or (lead.get("website_url") or "").strip()
    )
    qa_has = bool((lead.get("qa_checklist") or {}).get("passed"))
    qa_no = bool((lead.get("qa_no_website") or {}).get("passed"))

    if not has_site and qa_no:
        return "chain_b"
    if has_site or qa_has:
        return "chain_a"
    # ambiguous — fall through to has-website path
    return "chain_a"


def classify_reply(text: str) -> str:
    """Return 'hot' | 'dnc' | 'cold' for a given inbound reply body."""
    if not text:
        return "cold"
    t = text.strip()
    if _DNC_RE.search(t):
        return "dnc"
    if _HOT_RE.search(t):
        return "hot"
    return "cold"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _touch_offset(touch_n: int) -> timedelta:
    """How long after touch #1 should touch_n fire?"""
    if touch_n <= 1:
        return timedelta(0)
    idx = min(touch_n - 1, len(CHAIN_SCHEDULE_DAYS) - 1)
    return timedelta(days=CHAIN_SCHEDULE_DAYS[idx])


def _variant(chain_id: str, touch_n: int) -> Dict[str, str]:
    table = _CHAIN_A_VARIANTS if chain_id == "chain_a" else _CHAIN_B_VARIANTS
    return table.get(touch_n, {"subject_prefix": "", "sms_suffix": ""})


# ─────────────────────────────────────────────────────────────────────
# Chain state machine
# ─────────────────────────────────────────────────────────────────────

async def start_chain(
    db, lead: Dict[str, Any], *, source: str = "auto",
) -> Dict[str, Any]:
    """Fire touch #1 + persist initial chain state."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    lead_id = lead.get("lead_id")
    if not lead_id:
        return {"ok": False, "error": "lead_id missing"}

    chain_id = assign_chain(lead)
    started = _now()
    next_at = started + _touch_offset(2) if len(CHAIN_SCHEDULE_DAYS) > 1 else None

    # Fire touch #1 immediately
    fire = await _fire_touch(db, lead, chain_id, touch_n=1, source=source)

    chain_state = {
        "id": chain_id,
        "started_at": started.isoformat(),
        "touches": [{
            "n": 1,
            "sent_at": started.isoformat(),
            "sent_count": fire.get("sent_count", 0),
            "results": fire.get("results", {}),
        }],
        "next_touch_n": 2 if len(CHAIN_SCHEDULE_DAYS) > 1 else None,
        "next_touch_at": next_at.isoformat() if next_at else None,
        "completed": len(CHAIN_SCHEDULE_DAYS) <= 1,
        "halted_reason": None,
    }
    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "blast_chain": chain_state,
            "last_blast_at": started,
        }},
    )

    # Phase 1 — emit BLAST_SENT so Followup ORA can arm Day 2/5/9 +
    # heartbeat envoy. Fire-and-forget; never blocks the chain.
    try:
        from services.agent_registry import heartbeat, log_action
        from services.a2a_bus import bus
        import asyncio as _asyncio
        _asyncio.create_task(_asyncio.gather(
            heartbeat("envoy"),
            log_action("envoy", "BLAST_SENT",
                       f"chain={chain_id} sent={fire.get('sent_count', 0)}",
                       lead_id=lead_id,
                       metadata={"chain_id": chain_id, "touch_n": 1}),
            bus.emit("envoy", "BLAST_SENT", {
                "lead_id": lead_id,
                "chain_id": chain_id,
                "sent_count": fire.get("sent_count", 0),
            }),
            return_exceptions=True,
        ))
    except Exception:
        pass

    return {"ok": True, "chain": chain_state, "fire": fire}


async def advance_chain(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """Fire the next-due touch (idempotent if already past schedule)."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    lead_id = lead.get("lead_id")
    chain = (lead.get("blast_chain") or {})
    if chain.get("completed") or chain.get("halted_reason"):
        return {"ok": False, "error": "chain_already_done"}
    touch_n = int(chain.get("next_touch_n") or 0)
    if touch_n < 2:
        return {"ok": False, "error": "no_next_touch"}

    fire = await _fire_touch(db, lead, chain.get("id", "chain_a"),
                             touch_n=touch_n, source="chain")
    sent_at = _now()

    touches = list(chain.get("touches") or [])
    touches.append({
        "n": touch_n,
        "sent_at": sent_at.isoformat(),
        "sent_count": fire.get("sent_count", 0),
        "results": fire.get("results", {}),
    })

    is_last = touch_n >= len(CHAIN_SCHEDULE_DAYS)
    next_n = None if is_last else touch_n + 1
    next_at = (
        None if is_last
        else (datetime.fromisoformat(chain["started_at"])
              + _touch_offset(next_n)).isoformat()
    )

    new_state = {
        **chain,
        "touches": touches,
        "next_touch_n": next_n,
        "next_touch_at": next_at,
        "completed": is_last,
    }
    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {"blast_chain": new_state, "last_blast_at": sent_at}},
    )
    return {"ok": True, "chain": new_state, "fire": fire}


async def halt_chain(db, lead_id: str, reason: str) -> None:
    """Mark a chain as halted ('hot' or 'dnc')."""
    if db is None or not lead_id:
        return
    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "blast_chain.halted_reason": reason,
            "blast_chain.next_touch_at": None,
            "blast_chain.next_touch_n": None,
            "blast_chain.completed": True,
        }},
    )


# ─────────────────────────────────────────────────────────────────────
# Touch firing — wraps existing campaign_router blast logic
# ─────────────────────────────────────────────────────────────────────

async def _fire_touch(
    db, lead: Dict[str, Any], chain_id: str, *, touch_n: int, source: str,
) -> Dict[str, Any]:
    """Fire one touch via the existing channel renderer + sender pipeline.

    Mutates a copy of the lead with the per-touch subject_prefix + sms_suffix
    so downstream renderers vary the wording — without forking the templates.
    """
    var = _variant(chain_id, touch_n)
    augmented = dict(lead)
    # Stamp the per-touch hints; existing render_blast_artifacts /
    # execute_blast_for_lead can read these to flavour copy if they wish.
    augmented["touch_n"] = touch_n
    augmented["chain_id"] = chain_id
    augmented["touch_subject_prefix"] = var["subject_prefix"]
    augmented["touch_sms_suffix"] = var["sms_suffix"]
    # Lightweight inline subject/sms variation: prepend / append on the
    # already-rendered fields so the existing engine doesn't need to know
    # about chains.
    if augmented.get("blast_email_subject"):
        augmented["blast_email_subject"] = (
            var["subject_prefix"] + augmented["blast_email_subject"]
        )
    if augmented.get("blast_sms_body"):
        augmented["blast_sms_body"] = (
            augmented["blast_sms_body"] + var["sms_suffix"]
        )

    try:
        from routers.campaign_router import execute_blast_for_lead
        res = await asyncio.wait_for(
            execute_blast_for_lead(
                db, augmented, respect_gating=True, source=source,
            ),
            timeout=TOUCH_TIMEOUT_S,
        )
        return res or {}
    except asyncio.TimeoutError:
        logger.warning(f"[chain] touch #{touch_n} TIMEOUT for {lead.get('lead_id')}")
        return {"sent_count": 0, "error": "timeout"}
    except Exception as e:
        logger.warning(f"[chain] touch #{touch_n} failed for {lead.get('lead_id')}: {e}")
        return {"sent_count": 0, "error": type(e).__name__}


# ─────────────────────────────────────────────────────────────────────
# Reply handler
# ─────────────────────────────────────────────────────────────────────

async def handle_reply(
    db, lead_id: str, *, channel: str, text: str,
    from_addr: str = "",
) -> Dict[str, Any]:
    """Classify reply, halt chain, fire side-effects (DNC/Telegram)."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    cls = classify_reply(text)
    record = {
        "lead_id": lead_id,
        "channel": channel,
        "text": text[:2000],
        "from": from_addr,
        "classification": cls,
        "ts": _now(),
    }
    try:
        await db.blast_replies.insert_one(record.copy())
    except Exception as e:
        logger.debug(f"[chain] reply persist skipped: {e}")

    if cls == "hot":
        await db.campaign_leads.update_one(
            {"lead_id": lead_id},
            {"$set": {
                "hot_lead_flag": True,
                "hot_lead_at": _now(),
                "status": "interested",
            }},
        )
        await halt_chain(db, lead_id, "hot")
        # Phase 1 — parallel: telegram alert + emit HOT_REPLY (Closer arms call)
        try:
            from services.a2a_bus import bus
            await asyncio.gather(
                _telegram_hot_alert(lead_id, channel, text, from_addr),
                bus.emit("envoy", "HOT_REPLY", {
                    "lead_id": lead_id, "channel": channel,
                    "text": text[:500], "trigger": "hot_reply",
                }),
                return_exceptions=True,
            )
        except Exception:
            await _telegram_hot_alert(lead_id, channel, text, from_addr)
    elif cls == "dnc":
        # Add to do_not_contact + halt
        lead = await db.campaign_leads.find_one(
            {"lead_id": lead_id}, {"_id": 0, "phone": 1, "email": 1},
        ) or {}
        dnc_doc = {
            "lead_id": lead_id,
            "phone": lead.get("phone") or "",
            "email": (lead.get("email") or "").lower(),
            "reason": f"reply:{channel}:{text[:120]}",
            "ts": _now(),
        }
        try:
            await db.do_not_contact.update_one(
                {"$or": [{"phone": dnc_doc["phone"]},
                         {"email": dnc_doc["email"]}]},
                {"$set": dnc_doc},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[chain] dnc upsert skipped: {e}")
        await db.campaign_leads.update_one(
            {"lead_id": lead_id},
            {"$set": {"status": "unsubscribed", "dnc": True}},
        )
        await halt_chain(db, lead_id, "dnc")
        # Phase 1 — emit DNC_REPLY for ORA Brain learning
        try:
            from services.a2a_bus import bus
            await bus.emit("envoy", "DNC_REPLY", {
                "lead_id": lead_id, "channel": channel,
            })
        except Exception:
            pass

    return {"ok": True, "classification": cls}


async def _telegram_hot_alert(
    lead_id: str, channel: str, text: str, from_addr: str,
) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return
    msg = (
        "🔥 HOT LEAD reply!\n"
        f"Lead: {lead_id}\n"
        f"Channel: {channel}\n"
        f"From: {from_addr or '(unknown)'}\n"
        f"Text: {text[:500]}"
    )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=6.0) as c:
            await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": msg},
            )
    except Exception as e:
        logger.debug(f"[chain] telegram hot alert skipped: {e}")


# ─────────────────────────────────────────────────────────────────────
# Cycle helpers — used by the scheduler
# ─────────────────────────────────────────────────────────────────────

async def _due_chain_leads(db, limit: int = 50) -> List[Dict[str, Any]]:
    """Find leads whose next_touch_at is in the past and chain is active."""
    now_iso = _now().isoformat()
    q = {
        "blast_chain.next_touch_at": {"$lte": now_iso, "$ne": None},
        "blast_chain.completed": {"$ne": True},
        "blast_chain.halted_reason": {"$in": [None, ""]},
    }
    return await db.campaign_leads.find(q, {"_id": 0}).limit(limit).to_list(limit)


async def run_chain_advance_cycle(limit: int = 50) -> Dict[str, Any]:
    """Pick all leads whose next touch is due and advance them."""
    from services.auto_blast_engine import _get_db  # reuse
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db not ready"}

    leads = await _due_chain_leads(db, limit)
    advanced = 0
    sent = 0
    for lead in leads:
        try:
            r = await advance_chain(db, lead)
            if r.get("ok"):
                advanced += 1
                sent += int((r.get("fire") or {}).get("sent_count") or 0)
        except Exception as e:
            logger.warning(f"[chain] advance error for {lead.get('lead_id')}: {e}")
    return {"ok": True, "advanced": advanced, "sent": sent, "scanned": len(leads)}


async def chain_advance_scheduler():
    """Forever loop: every 5 min, fire any due touches."""
    print("[chain] advance scheduler alive — 45s grace before first cycle", flush=True)
    await asyncio.sleep(45)
    while True:
        try:
            res = await run_chain_advance_cycle(limit=100)
            if res.get("ok") and (res.get("advanced") or 0) > 0:
                print(
                    f"[chain] cycle: scanned={res.get('scanned')} "
                    f"advanced={res.get('advanced')} sent={res.get('sent')}",
                    flush=True,
                )
            await asyncio.sleep(300)  # 5 min
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[chain] scheduler error: {e}", exc_info=True)
            await asyncio.sleep(120)
