"""
ORA Phase 2.5 — Sovereign Customer Handler
==============================================
Five capabilities, one cohesive module:

  A. Proactive Retention   — detect at-risk customers, queue check-ins
  B. Autonomous Upsell     — detect heavy users, queue plan-upgrade pitches
  C. Omnichannel Context   — channel-aware memory keyed by user (not session)
  D. Predictive Next Action — Claude generates one suggested action per turn
  E. Guardian Policy Check — pre-flight CASL/budget/brand/PII gate

iter 281.5 — wires existing pieces (sentiment, churn, three-tier memory,
Resend, Twilio WhatsApp, Stripe checkout) — no new infra.

Schedulers run inside the FastAPI loop via APScheduler (already used by
ora_self_heal + autonomous_repair_engine).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tunables (env-overridable) ─────────────────────────────────────
RETENTION_LOGIN_GAP_DAYS = int(os.environ.get("ORA_RETENTION_LOGIN_GAP_DAYS", "3"))
RETENTION_INVOICE_OVERDUE_DAYS = int(os.environ.get("ORA_RETENTION_INVOICE_GAP_DAYS", "7"))
CHURN_RISK_THRESHOLD = float(os.environ.get("ORA_CHURN_THRESHOLD", "0.7"))
UPSELL_USAGE_DAYS = int(os.environ.get("ORA_UPSELL_DAYS", "60"))
GUARDIAN_DAILY_BUDGET_CENTS = int(os.environ.get("ORA_DAILY_BUDGET_CENTS", "20000"))
RETENTION_SCAN_MINUTES = int(os.environ.get("ORA_RETENTION_SCAN_MINUTES", "30"))
UPSELL_SCAN_MINUTES = int(os.environ.get("ORA_UPSELL_SCAN_MINUTES", "120"))


# ─────────────────────────────────────────────────────────────────
# E. Guardian Policy Check (pre-flight)
# ─────────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),                # SSN
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),                        # credit card
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b"),                # IBAN-ish
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
]
_BRAND_BANNED = re.compile(
    r"\b(guarantee|risk[-\s]?free|100%\s*money[-\s]?back|miracle|"
    r"unlimited|click here|act now|limited time)\b",
    re.IGNORECASE,
)


async def guardian_check(
    db,
    *,
    action_kind: str,
    target: str,
    body: str = "",
    cost_cents: int = 0,
    channel: str = "chat",
) -> Dict[str, Any]:
    """Run all policy gates. Returns:
       {allowed: bool, reason: str|None, fixes: dict, cost_cents}
    """
    fixes: Dict[str, Any] = {}
    reasons: List[str] = []

    # 1. CASL opt-out (email or whatsapp)
    if action_kind in ("email", "whatsapp", "sms") and target and db is not None:
        try:
            optout = await db.casl_optouts.find_one(
                {"target": target.lower().strip()}
            )
            if optout:
                reasons.append(f"casl_opt_out:{target}")
        except Exception:
            pass

    # 2. Daily budget cap (sum of cost in last 24h)
    if cost_cents > 0 and db is not None:
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            pipeline = [
                {"$match": {"created_at": {"$gte": since.isoformat()}}},
                {"$group": {"_id": None, "total": {"$sum": "$cost_cents"}}},
            ]
            agg = [r async for r in db.ora_policy_log.aggregate(pipeline)]
            spent = int((agg[0].get("total") if agg else 0) or 0)
            if spent + cost_cents > GUARDIAN_DAILY_BUDGET_CENTS:
                reasons.append(f"budget_exceeded:{spent + cost_cents}c > {GUARDIAN_DAILY_BUDGET_CENTS}c")
        except Exception:
            pass

    # 3. PII leakage in outbound body
    if body and action_kind in ("email", "whatsapp", "sms"):
        for rgx in _PII_PATTERNS:
            if rgx.search(body):
                reasons.append("pii_in_outbound_body")
                break

    # 4. Brand-tone violations (banned salesy phrases)
    if body and _BRAND_BANNED.search(body):
        cleaned = _BRAND_BANNED.sub("", body)
        fixes["sanitized_body"] = cleaned.strip()
        reasons.append("brand_tone_phrase_used")

    allowed = not reasons or (
        # If only fix is a sanitization, we can auto-fix and proceed
        len(reasons) == 1 and reasons[0] == "brand_tone_phrase_used" and "sanitized_body" in fixes
    )
    decision = {
        "allowed": allowed,
        "reason": "; ".join(reasons) if reasons else None,
        "fixes": fixes,
        "cost_cents": cost_cents,
        "action_kind": action_kind,
        "target": target,
        "channel": channel,
        "ts": datetime.now(timezone.utc).isoformat(),
    }

    # Persist every decision (audit trail)
    if db is not None:
        try:
            await db.ora_policy_log.insert_one({
                **decision,
                "body_excerpt": (body or "")[:240],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
    return decision


# ─────────────────────────────────────────────────────────────────
# C. Omnichannel Context — channel-aware memory keyed by USER
# ─────────────────────────────────────────────────────────────────
async def remember_omni_context(
    db,
    *,
    user: str,
    channel: str,
    text: str,
    intent: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> None:
    """Append to db.ora_omni_context keyed by user (not session).
    Keeps last 30 turns across all channels. The next time the same
    user pings ORA from any channel, this context is loaded and
    fed into Hermes RAG so they don't repeat themselves.
    """
    if db is None or not user:
        return
    try:
        turn = {
            "channel": channel,
            "text": (text or "")[:1000],
            "intent": intent,
            "sentiment": sentiment,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await db.ora_omni_context.update_one(
            {"user": user},
            {
                "$push": {"turns": {"$each": [turn], "$slice": -30}},
                "$set": {"last_channel": channel, "last_at": turn["ts"]},
                "$setOnInsert": {"user": user, "created_at": turn["ts"]},
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[ora-25] omni context save failed: {e}")


async def load_omni_context(db, *, user: str, max_turns: int = 10) -> Dict[str, Any]:
    if db is None or not user:
        return {"turns": []}
    try:
        doc = await db.ora_omni_context.find_one(
            {"user": user},
            {"_id": 0, "turns": {"$slice": -max_turns}, "last_channel": 1, "last_at": 1},
        )
        return doc or {"turns": []}
    except Exception:
        return {"turns": []}


# ─────────────────────────────────────────────────────────────────
# D. Predictive Next-Best-Action
# ─────────────────────────────────────────────────────────────────
async def generate_next_action(
    db,
    *,
    user: str,
    context_text: str,
    last_intent: Optional[str] = None,
    sentiment: Optional[str] = None,
) -> Dict[str, Any]:
    """Claude generates ONE recommended next action."""
    omni = await load_omni_context(db, user=user, max_turns=5)
    summary = "\n".join(
        f"[{t.get('channel')}] {t.get('text', '')[:120]}"
        for t in (omni.get("turns") or [])[-5:]
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"nba_{uuid.uuid4()}",
            system_message=(
                "You are ORA's strategic advisor. Given recent customer context, "
                "output a single recommended next action in this format:\n"
                "  action=<call|email|whatsapp|wait|upsell|none>; "
                "when=<asap|today|tomorrow_morning|specific_time>; "
                "reason=<one short sentence>\n"
                "No prose, no preamble, just the line."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        prompt = (
            f"Customer: {user}\n"
            f"Last sentiment: {sentiment or 'unknown'}\n"
            f"Last intent: {last_intent or 'unknown'}\n"
            f"Recent context:\n{summary or '(no prior context)'}\n"
            f"Latest message: {context_text[:300]}\n"
        )
        out = (await chat.send_message(UserMessage(text=prompt))).strip()
        m_action = re.search(r"action=(\w+)", out, re.I)
        m_when = re.search(r"when=(\w+)", out, re.I)
        m_reason = re.search(r"reason=(.+?)(?:;|$)", out, re.I)
        nba = {
            "action": (m_action.group(1).lower() if m_action else "wait"),
            "when": (m_when.group(1).lower() if m_when else "today"),
            "reason": (m_reason.group(1).strip() if m_reason else "no specific signal"),
            "raw": out,
            "for_user": user,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.debug(f"[ora-25] nba LLM failed: {e}")
        nba = {
            "action": "wait",
            "when": "today",
            "reason": "LLM unavailable — defaulting to wait",
            "for_user": user,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    if db is not None:
        try:
            await db.ora_next_actions.insert_one({
                **nba,
                "context_excerpt": (context_text or "")[:240],
            })
        except Exception:
            pass
    return nba


# ─────────────────────────────────────────────────────────────────
# A. Proactive Retention Engine (background scan)
# ─────────────────────────────────────────────────────────────────
async def scan_retention_candidates(db) -> List[Dict[str, Any]]:
    """Find customers who need a check-in.
    Returns a list of candidate dicts with reason + suggested message stub.
    """
    if db is None:
        return []
    candidates: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # 1) Login gap — platform_users with stale last_login
    try:
        threshold = (now - timedelta(days=RETENTION_LOGIN_GAP_DAYS)).isoformat()
        cursor = db.platform_users.find(
            {"last_login": {"$lt": threshold}, "active": {"$ne": False}},
            {"_id": 0, "email": 1, "phone": 1, "last_login": 1, "business_name": 1},
        ).limit(40)
        async for u in cursor:
            candidates.append({
                "kind": "login_gap",
                "email": u.get("email"),
                "phone": u.get("phone"),
                "last_login": u.get("last_login"),
                "biz": u.get("business_name") or u.get("email"),
                "suggested_msg": (
                    f"Hi {u.get('business_name') or 'boss'}, AUREM here. We noticed "
                    f"you haven't logged in for a few days. Need help getting back on track?"
                ),
            })
    except Exception as e:
        logger.debug(f"[ora-25] retention login_gap failed: {e}")

    # 2) Invoice overdue
    try:
        overdue_cutoff = (now - timedelta(days=RETENTION_INVOICE_OVERDUE_DAYS)).isoformat()
        cursor = db.payment_transactions.find(
            {"status": {"$in": ["pending", "open", "past_due"]}, "created_at": {"$lt": overdue_cutoff}},
            {"_id": 0, "user_email": 1, "amount_cents": 1, "created_at": 1},
        ).limit(40)
        async for t in cursor:
            email = t.get("user_email")
            if not email:
                continue
            candidates.append({
                "kind": "invoice_overdue",
                "email": email,
                "amount_cents": t.get("amount_cents"),
                "since": t.get("created_at"),
                "suggested_msg": (
                    f"Hi {email}, an invoice on your AUREM account is "
                    f"{RETENTION_INVOICE_OVERDUE_DAYS}+ days overdue. Sorting it out "
                    f"now keeps your services active. Reply to settle in 1 click."
                ),
            })
    except Exception as e:
        logger.debug(f"[ora-25] retention invoice failed: {e}")

    # 3) Churn-risk score (use existing churn collection if present)
    try:
        cursor = db.churn_predictions.find(
            {"score": {"$gte": CHURN_RISK_THRESHOLD}, "actioned_at": {"$exists": False}},
            {"_id": 0, "tenant_id": 1, "email": 1, "score": 1},
        ).limit(20)
        async for c in cursor:
            candidates.append({
                "kind": "churn_risk",
                "email": c.get("email"),
                "tenant_id": c.get("tenant_id"),
                "score": c.get("score"),
                "suggested_msg": (
                    "We have a special offer for valued customers — let's chat about "
                    "how to lock in your AUREM plan at a better rate."
                ),
            })
    except Exception:
        pass

    # Persist candidates as queued actions (idempotent on (kind,email))
    if candidates:
        for c in candidates:
            try:
                await db.ora_retention_actions.update_one(
                    {"kind": c["kind"], "email": c.get("email")},
                    {
                        "$setOnInsert": {
                            **c,
                            "status": "queued",
                            "created_at": now.isoformat(),
                        },
                    },
                    upsert=True,
                )
            except Exception:
                pass
    return candidates


# ─────────────────────────────────────────────────────────────────
# B. Autonomous Upsell
# ─────────────────────────────────────────────────────────────────
async def scan_upsell_candidates(db) -> List[Dict[str, Any]]:
    if db is None:
        return []
    candidates: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # Starter plan + 60-day tenure + recent positive sentiment → Growth pitch
    try:
        cutoff = (now - timedelta(days=UPSELL_USAGE_DAYS)).isoformat()
        cursor = db.customer_subscriptions.find(
            {
                "plan": {"$in": ["starter", "lite", "site_monitor_lite"]},
                "status": {"$in": ["active", "paid"]},
                "created_at": {"$lt": cutoff},
            },
            {"_id": 0, "email": 1, "plan": 1, "created_at": 1},
        ).limit(30)
        async for s in cursor:
            email = s.get("email")
            if not email:
                continue
            sentiment = "neutral"
            try:
                last_sent = await db.sentiment_history.find_one(
                    {"email": email}, sort=[("ts", -1)], projection={"_id": 0, "label": 1}
                )
                sentiment = (last_sent or {}).get("label", "neutral")
            except Exception:
                pass
            if sentiment == "negative":
                continue  # don't upsell unhappy customers
            candidates.append({
                "kind": "upgrade_starter_to_growth",
                "email": email,
                "current_plan": s.get("plan"),
                "suggested_plan": "growth",
                "sentiment": sentiment,
                "suggested_msg": (
                    "We noticed your usage has grown — the Growth plan unlocks more "
                    "headroom and saves on per-unit cost. Want a one-click upgrade link?"
                ),
            })
    except Exception as e:
        logger.debug(f"[ora-25] upsell starter failed: {e}")

    # 5+ successful bookings → Enterprise pitch
    try:
        cursor = db.bookings.aggregate([
            {"$match": {"status": "completed"}},
            {"$group": {"_id": "$email", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": 5}}},
            {"$limit": 20},
        ])
        async for b in cursor:
            candidates.append({
                "kind": "upgrade_to_enterprise",
                "email": b.get("_id"),
                "completed_bookings": b.get("n"),
                "suggested_plan": "enterprise",
                "suggested_msg": (
                    "You're hitting Enterprise volumes. Let's lock in a custom contract "
                    "with priority support and a dedicated rep."
                ),
            })
    except Exception:
        pass

    if candidates:
        for c in candidates:
            try:
                await db.ora_upsell_actions.update_one(
                    {"kind": c["kind"], "email": c.get("email")},
                    {"$setOnInsert": {**c, "status": "queued", "created_at": now.isoformat()}},
                    upsert=True,
                )
            except Exception:
                pass
    return candidates


# ─────────────────────────────────────────────────────────────────
# Background scheduler hooks
# ─────────────────────────────────────────────────────────────────
def attach_phase_25_scheduler(scheduler, db):
    """Register periodic retention + upsell scans on the existing scheduler."""
    if scheduler is None or db is None:
        return False

    async def _retention_tick():
        try:
            n = len(await scan_retention_candidates(db))
            if n:
                logger.info(f"[ora-25/retention] tick — {n} candidates queued")
        except Exception as e:
            logger.warning(f"[ora-25/retention] tick failed: {e}")

    async def _upsell_tick():
        try:
            n = len(await scan_upsell_candidates(db))
            if n:
                logger.info(f"[ora-25/upsell] tick — {n} candidates queued")
        except Exception as e:
            logger.warning(f"[ora-25/upsell] tick failed: {e}")

    try:
        scheduler.add_job(
            _retention_tick,
            trigger="interval",
            minutes=RETENTION_SCAN_MINUTES,
            id="ora_25_retention",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        scheduler.add_job(
            _upsell_tick,
            trigger="interval",
            minutes=UPSELL_SCAN_MINUTES,
            id="ora_25_upsell",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(minutes=4),
        )
        logger.info(
            "[ora-25] scheduler attached — retention every %sm, upsell every %sm",
            RETENTION_SCAN_MINUTES, UPSELL_SCAN_MINUTES,
        )
        return True
    except Exception as e:
        logger.warning(f"[ora-25] scheduler attach failed: {e}")
        return False
