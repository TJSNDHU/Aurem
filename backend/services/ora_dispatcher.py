"""
ORA Dispatcher — Autonomous Agentic Orchestrator
=================================================

Transforms ORA from a RAG assistant into a Jarvis-style
orchestrator that classifies intents and delegates to
specialized agents (Scout, Envoy, Closer, Oracle, Architect).

Token Efficiency:
  - Reads pre-computed daily summaries (~50 tokens)
    instead of raw CRM dumps (~5,000 tokens)
  - Delegates execution to agents; ORA stays lean

Audit:
  - Every dispatched action is hashed via the blockchain audit trail.
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


# ═══════════════════════════════════════════════════
# INTENT → AGENT MAP
# ═══════════════════════════════════════════════════

INTENT_AGENT_MAP = {
    "FOLLOW_UP":      "envoy",
    "OUTREACH":       "envoy",
    "PIPELINE_CHECK": "closer",
    "DEAL_ANALYSIS":  "closer",
    "LEAD_SCORE":     "scout",
    "LEAD_DISCOVERY": "scout",
    "FORECAST":       "oracle",
    "PREDICT":        "oracle",
    "STATUS_REPORT":  "oracle",
    "SYSTEM_AUDIT":   "architect",
    "OPTIMIZE":       "architect",
    "SOCIAL_SCAN":    "scout",
}

# Keywords that trigger delegation (intent classification)
DELEGATION_SIGNALS = {
    "FOLLOW_UP":      ["follow up", "follow-up", "reach out", "send email", "contact them", "send a message", "touch base"],
    "OUTREACH":       ["outreach", "engage", "draft email", "cold email", "introduction email", "send intro"],
    "PIPELINE_CHECK": ["pipeline", "how are deals", "deal status", "deal health", "at risk", "deals looking"],
    "DEAL_ANALYSIS":  ["analyze deal", "close deal", "closing strategy", "proposal", "negotiate", "win probability"],
    "LEAD_SCORE":     ["score leads", "score our leads", "qualify leads", "rank leads", "best leads", "lead quality", "prioritize lead", "which leads"],
    "LEAD_DISCOVERY": ["find leads", "new leads", "discover leads", "prospect", "generate leads"],
    "FORECAST":       ["forecast", "predict revenue", "next month", "projection", "revenue trend", "revenue forecast"],
    "PREDICT":        ["predict", "what will", "expected", "churn risk", "churn prediction"],
    "STATUS_REPORT":  ["how are we doing", "status report", "how's business", "business status", "give me a status", "how is business", "where do we stand", "performance report", "quarterly update", "how are things", "give me an update"],
    "SYSTEM_AUDIT":   ["audit", "system check", "health check", "collections", "database status"],
    "OPTIMIZE":       ["optimize", "improve workflow", "automate", "workflow design", "efficiency"],
    "SOCIAL_SCAN":    ["scan social", "social media scan", "social profile", "check their linkedin", "check their twitter", "check their instagram", "check their facebook", "social media", "linkedin profile", "twitter profile", "instagram profile", "facebook profile", "scan their social", "social deep scan", "analyze social", "social media analysis"],
}


def classify_intent(message: str) -> Dict:
    """
    Classify user message into a dispatchable intent.

    Returns:
        {
            "intent": "FOLLOW_UP" | "PIPELINE_CHECK" | ... | "CONVERSATIONAL",
            "agent": "envoy" | "closer" | ... | None,
            "confidence": float,
            "should_delegate": bool
        }
    """
    msg_lower = message.lower()

    for intent, keywords in DELEGATION_SIGNALS.items():
        matched = [kw for kw in keywords if kw in msg_lower]
        if matched:
            return {
                "intent": intent,
                "agent": INTENT_AGENT_MAP[intent],
                "confidence": min(0.75 + len(matched) * 0.05, 0.95),
                "should_delegate": True,
                "matched_keywords": matched,
            }

    return {
        "intent": "CONVERSATIONAL",
        "agent": None,
        "confidence": 0.6,
        "should_delegate": False,
        "matched_keywords": [],
    }


# ═══════════════════════════════════════════════════
# DISPATCHER — Task Handover Protocol
# ═══════════════════════════════════════════════════

async def dispatch(intent: str, agent_id: str, params: dict = None) -> Dict:
    """
    Delegate execution to a specialized agent.

    ORA calls this instead of doing the work itself.
    Results are audited via the blockchain trail.
    """
    db = get_db()
    if db is None:
        return {"success": False, "error": "Database not initialized"}

    params = params or {}

    # Import agent executors
    from routers.agent_execution_router import (
        AGENT_EXECUTORS,
        create_audit_entry,
    )

    executor = AGENT_EXECUTORS.get(agent_id)
    if not executor:
        return {"success": False, "error": f"Unknown agent: {agent_id}"}

    # ═══ PLANNING HEADER (Vibe Coding: Clarify Scope Before Execution) ═══
    # Scout and Envoy get a pre-execution planning directive
    if agent_id in ("scout", "envoy"):
        planning_scope = {
            "scout": "Discover and score leads. Prioritize by fit (company size, industry match). Flag data gaps. Report confidence per lead.",
            "envoy": "Draft outreach for top-scored leads ONLY. Match brand voice (Scientific-Luxe). Personalize per lead context. Block generic templates.",
        }
        params["planning_directive"] = planning_scope.get(agent_id, "")
        params["quality_bar"] = "CEO-grade output. No filler. Every action must be verifiable."

    try:
        result = await executor(params, db)

        # ═══ DYNAMIC AGENT CONFIDENCE ROUTING ═══
        # Score < 70: add human confirmation before executing
        # Score > 85: direct execution, no confirmation needed
        agent_skill = await _get_agent_skill(db, agent_id)
        if agent_skill < 70:
            # Low-score agent: flag output for human review
            result["requires_confirmation"] = True
            result["confidence_note"] = (
                f"{agent_id.upper()} agent score is {agent_skill}/100. "
                f"Output flagged for human confirmation before execution."
            )
            logger.info(f"[ORA Dispatcher] {agent_id} score={agent_skill} → CONFIRMATION REQUIRED")
        elif agent_skill > 85:
            result["requires_confirmation"] = False
            result["confidence_note"] = f"{agent_id.upper()} agent score is {agent_skill}/100. Direct execution."
            logger.info(f"[ORA Dispatcher] {agent_id} score={agent_skill} → DIRECT EXECUTION")

        # ═══ CRITIC VALIDATION HOOK (Zero-Trust Layer) ═══
        # Every agent output is reviewed before reaching the user.
        # Uses OpenRouter free-tier consensus for $0 cost.
        critic_review = None
        try:
            from services.critic_agent import (
                validate_agent_output, consensus_validate_agent_output,
                rescue_fallback, set_db as set_critic_db,
            )
            set_critic_db(db)

            # Check confidence — if agent reports it
            agent_confidence = result.get("confidence", 0.8)

            if agent_confidence < 0.7:
                # RESCUE: Low confidence → get second opinion
                rescue = await rescue_fallback(agent_id, result, agent_confidence)
                critic_review = {
                    "mode": "rescue",
                    "rescue_verdict": rescue.get("rescue_verdict", "ACCEPTED"),
                    "adjusted_confidence": rescue.get("adjusted_confidence", agent_confidence),
                    "corrections": rescue.get("corrections", []),
                }
                logger.info(f"[Critic] RESCUE for {agent_id}: {rescue.get('rescue_verdict')}")
            elif agent_id == "envoy":
                # ENVOY: Use consensus validation (dual-model, zero cost)
                validation = await consensus_validate_agent_output(agent_id, intent, result)
                critic_review = {
                    "mode": "consensus",
                    "verdict": validation.get("verdict", "UNKNOWN"),
                    "confidence": validation.get("confidence", 0.5),
                    "passed": validation.get("passed", True),
                    "agreement": validation.get("review", {}).get("agreement", False),
                }
                logger.info(f"[Critic] CONSENSUS {agent_id} → {validation.get('verdict')}")
            else:
                # VALIDATE: Standard single-model critic review
                validation = await validate_agent_output(agent_id, intent, result)
                critic_review = {
                    "mode": "validate",
                    "verdict": validation.get("verdict", "UNKNOWN"),
                    "confidence": validation.get("confidence", 0.5),
                    "issues_count": len(validation.get("review", {}).get("issues", [])),
                    "passed": validation.get("passed", True),
                }
                logger.info(f"[Critic] {agent_id} → {validation.get('verdict')}")
        except Exception as critic_err:
            logger.warning(f"[Critic] Review error (non-blocking): {critic_err}")

        # ═══ ENVOY HARD GATE (approval_score > 0.8) ═══
        # Envoy outreach BLOCKED unless Critic approves with high confidence.
        if agent_id == "envoy" and critic_review:
            approval_score = critic_review.get("confidence", 0)
            verdict = critic_review.get("verdict", "UNKNOWN")

            if verdict != "APPROVED" or approval_score <= 0.8:
                logger.warning(
                    f"[ORA] ENVOY BLOCKED: verdict={verdict}, score={approval_score:.2f}"
                )
                await create_audit_entry(
                    db,
                    action="envoy_blocked_by_critic",
                    agent_id="critic",
                    data={
                        "verdict": verdict,
                        "approval_score": approval_score,
                        "threshold": 0.8,
                        "reason": "Outreach quality below threshold",
                    },
                )
                return {
                    "success": False,
                    "agent": "envoy",
                    "intent": intent,
                    "blocked": True,
                    "reason": (
                        f"Critic blocked outreach (score: {approval_score:.2f}, "
                        f"threshold: 0.80). Outreach must score > 0.80 for automated dispatch."
                    ),
                    "critic_review": critic_review,
                    "result": result,
                }

        # Audit trail — every dispatched action is hashed
        await create_audit_entry(
            db,
            action=f"ora_dispatch_{intent.lower()}",
            agent_id=agent_id,
            data={"intent": intent, "summary": result.get("summary", ""), "critic": critic_review},
        )

        logger.info(
            f"[ORA Dispatcher] {intent} → {agent_id}: {result.get('summary', 'done')}"
        )

        # ═══ PUSH NOTIFICATION TRIGGER ═══
        try:
            from services.push_notification_service import (
                notify_new_lead, notify_outreach_sent, set_db as set_push_db,
            )
            set_push_db(db)
            user_id = params.get("user_id", "admin")
            if agent_id == "scout" and result.get("summary"):
                await notify_new_lead(user_id, result.get("summary", "")[:60], "Scout")
            elif agent_id == "envoy" and not result.get("blocked"):
                await notify_outreach_sent(user_id, result.get("summary", "")[:60])
        except Exception as push_err:
            logger.debug(f"[ORA Dispatcher] Push notification error (non-blocking): {push_err}")

        return {
            "success": True,
            "agent": agent_id,
            "intent": intent,
            "result": result,
            "critic_review": critic_review,
        }

    except Exception as e:
        logger.error(f"[ORA Dispatcher] Execution error: {e}")
        return {"success": False, "agent": agent_id, "error": str(e)}


# ═══════════════════════════════════════════════════
# DAILY SUMMARY — Pre-Computed Context (Token Saver)
# ═══════════════════════════════════════════════════

async def generate_daily_summary() -> Dict:
    """
    Scout-generated daily business summary.

    Stored in MongoDB `daily_summaries` collection.
    ORA reads this 50-token summary instead of 5,000-token raw dumps.
    """
    db = get_db()
    if db is None:
        return {"error": "Database not initialized"}

    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Pipeline health
        open_deals = await db.deals.find(
            {"status": {"$nin": ["won", "lost"]}}, {"_id": 0, "value": 1, "stage": 1, "title": 1}
        ).to_list(500)

        total_pipeline = sum(d.get("value", 0) for d in open_deals)
        deal_count = len(open_deals)

        # Stage breakdown
        stages = {}
        for d in open_deals:
            s = d.get("stage", "unknown")
            stages[s] = stages.get(s, 0) + 1

        # At-risk: deals with no recent activity (placeholder heuristic)
        at_risk_count = sum(1 for d in open_deals if d.get("stage", "").lower() in ("scan",))

        # Won this month
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        won_deals = await db.deals.find(
            {"status": "won", "closed_at": {"$gte": month_start}},
            {"_id": 0, "value": 1},
        ).to_list(100)
        won_revenue = sum(d.get("value", 0) for d in won_deals)

        # Contacts / leads
        total_contacts = await db.contacts.count_documents({})
        scored_leads = await db.contacts.count_documents({"score": {"$exists": True}})
        high_quality = await db.contacts.count_documents({"grade": {"$in": ["A", "B"]}})

        # Sentiment pulse (from extracted service)
        recent_panics = await db.panic_events.count_documents(
            {"created_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}}
        )

        summary = {
            "date": today,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": {
                "total_value": total_pipeline,
                "deal_count": deal_count,
                "stages": stages,
                "at_risk": at_risk_count,
            },
            "revenue": {
                "won_this_month": won_revenue,
                "won_count": len(won_deals),
            },
            "contacts": {
                "total": total_contacts,
                "scored": scored_leads,
                "high_quality": high_quality,
            },
            "sentiment": {
                "panic_events_24h": recent_panics,
                "alert_level": "critical" if recent_panics > 3 else "elevated" if recent_panics > 0 else "calm",
            },
            "digest": (
                f"Pipeline: ${total_pipeline:,.0f} across {deal_count} deals "
                f"({at_risk_count} at risk). "
                f"Revenue this month: ${won_revenue:,.0f}. "
                f"Contacts: {total_contacts} ({high_quality} high-quality). "
                f"Sentiment: {'ALERT' if recent_panics > 0 else 'calm'}."
            ),
        }

        # Upsert into daily_summaries
        await db.daily_summaries.update_one(
            {"date": today},
            {"$set": summary},
            upsert=True,
        )

        logger.info(f"[ORA Dispatcher] Daily summary generated: {summary['digest']}")
        return summary

    except Exception as e:
        logger.error(f"[ORA Dispatcher] Daily summary error: {e}")
        return {"error": str(e)}


async def get_daily_summary() -> Optional[Dict]:
    """
    Retrieve today's pre-computed summary.
    Falls back to generating one on the fly if not found.
    """
    db = get_db()
    if db is None:
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = await db.daily_summaries.find_one(
        {"date": today}, {"_id": 0}
    )

    if not summary:
        summary = await generate_daily_summary()

    return summary


# ═══════════════════════════════════════════════════
# LEAN RAG CONTEXT (Summary-First Pattern)
# ═══════════════════════════════════════════════════

async def build_lean_context(query: str, intent_data: Dict) -> str:
    """
    Token-efficient context builder.

    Order:
    1. Read daily summary (~50 tokens)
    2. Only fetch raw data if the query needs detail beyond the summary
    """
    parts = []

    # Always: lean daily summary
    summary = await get_daily_summary()
    if summary:
        parts.append(f"[DAILY BRIEF] {summary.get('digest', '')}")

    # If the intent requires delegation, skip raw data (agent will handle it)
    if intent_data.get("should_delegate"):
        agent = intent_data.get("agent", "unknown")
        parts.append(
            f"[DISPATCH READY] Task will be delegated to {agent.upper()} agent."
        )
        return "\n".join(parts)

    # For conversational queries, fetch targeted context
    if intent_data.get("intent") == "CONVERSATIONAL":
        db = get_db()
        if db is not None:
            # Targeted data fetch based on keywords
            q_lower = query.lower()
            if any(w in q_lower for w in ("deal", "pipeline", "stage")):
                deals = await db.deals.find(
                    {"status": {"$nin": ["won", "lost"]}},
                    {"_id": 0, "title": 1, "value": 1, "stage": 1, "company": 1},
                ).sort("value", -1).limit(5).to_list(5)
                if deals:
                    parts.append("TOP DEALS:")
                    for d in deals:
                        parts.append(
                            f"  {d.get('title','-')} | {d.get('company','-')} | "
                            f"${d.get('value',0):,.0f} | {d.get('stage','-')}"
                        )

            if any(w in q_lower for w in ("lead", "contact", "customer")):
                contacts = await db.contacts.find(
                    {}, {"_id": 0, "name": 1, "company": 1, "grade": 1, "score": 1}
                ).sort("score", -1).limit(5).to_list(5)
                if contacts:
                    parts.append("TOP CONTACTS:")
                    for c in contacts:
                        parts.append(
                            f"  {c.get('name','-')} | {c.get('company','-')} | "
                            f"Grade: {c.get('grade','-')} | Score: {c.get('score','-')}"
                        )

    return "\n".join(parts) if parts else ""


# ═══════════════════════════════════════════════════
# DYNAMIC AGENT SKILL SCORING
# ═══════════════════════════════════════════════════

AGENT_DEFAULT_SCORES = {
    "scout": 72, "architect": 85, "envoy": 68,
    "closer": 77, "orchestrator": 90, "oracle": 80,
}


async def _get_agent_skill(db, agent_id: str) -> int:
    """
    Calculate dynamic agent skill from audit trail success rate.
    Falls back to default if < 5 total actions.
    """
    if db is None:
        return AGENT_DEFAULT_SCORES.get(agent_id, 75)

    total = await db.audit_trail.count_documents({"agent_id": agent_id})
    if total < 5:
        return AGENT_DEFAULT_SCORES.get(agent_id, 75)

    successful = await db.audit_trail.count_documents({
        "agent_id": agent_id,
        "$or": [
            {"data.critic.verdict": "APPROVED"},
            {"data.critic.passed": True},
            {"data.summary": {"$exists": True, "$ne": ""}},
        ],
    })
    return int((successful / total) * 100) if total > 0 else AGENT_DEFAULT_SCORES.get(agent_id, 75)
