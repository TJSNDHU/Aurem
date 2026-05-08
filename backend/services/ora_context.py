"""
ORA Context Loader
Loads full business context into session when user logs into ORA.
Makes ORA immediately personal with real data.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


async def load_business_context(db, tenant_id: str, user_doc: dict = None) -> dict:
    """Load full business context for ORA session."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    context = {
        "business_name": "",
        "business_id": "",
        "plan": "Starter",
        "ora_name": "ORA",
        "leads_today": [],
        "leads_count": 0,
        "pending_approvals": 0,
        "outstanding_invoices": 0,
        "outstanding_revenue": 0,
        "revenue_this_month": 0,
        "website_health_score": 0,
        "working_memory": None,
        "last_pipeline_run": None,
        "recent_actions": [],
        "todays_brief": None,
        "todays_brief_summary": "",
        "economic_context": None,
        "timezone": "America/Toronto",
        "language": "en",
        "notification_prefs": {},
    }

    if db is None:
        return context

    try:
        if user_doc:
            context["business_name"] = user_doc.get("company") or user_doc.get("company_name") or user_doc.get("business_name") or f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip()
            context["business_id"] = user_doc.get("business_id", "")
            context["timezone"] = user_doc.get("timezone", "America/Toronto")
        else:
            user_doc = await db.users.find_one(
                {"$or": [{"id": tenant_id}, {"tenant_id": tenant_id}]},
                {"_id": 0}
            )
            if user_doc:
                context["business_name"] = user_doc.get("company") or user_doc.get("company_name") or user_doc.get("business_name") or f"{user_doc.get('first_name', '')} {user_doc.get('last_name', '')}".strip()
                context["business_id"] = user_doc.get("business_id", "")
                context["timezone"] = user_doc.get("timezone", "America/Toronto")

        plan_doc = await db.tenant_plans.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if plan_doc:
            context["plan"] = plan_doc.get("plan_name", "Starter")

        leads_cursor = db.leads.find(
            {"tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()}},
            {"_id": 0, "name": 1, "company": 1, "score": 1, "city": 1}
        ).sort("score", -1).limit(3)
        leads = await leads_cursor.to_list(3)
        context["leads_today"] = leads
        context["leads_count"] = await db.leads.count_documents(
            {"tenant_id": tenant_id, "created_at": {"$gte": today_start.isoformat()}}
        )

        context["pending_approvals"] = await db.approval_queue.count_documents(
            {"tenant_id": tenant_id, "status": "pending"}
        )

        invoices = db.invoices.find(
            {"tenant_id": tenant_id, "status": {"$in": ["pending", "overdue"]}},
            {"_id": 0, "amount": 1}
        )
        inv_list = await invoices.to_list(100)
        context["outstanding_invoices"] = len(inv_list)
        context["outstanding_revenue"] = sum(i.get("amount", 0) for i in inv_list)

        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        revenue_cursor = db.invoices.find(
            {"tenant_id": tenant_id, "status": "paid", "paid_at": {"$gte": month_start.isoformat()}},
            {"_id": 0, "amount": 1}
        )
        rev_list = await revenue_cursor.to_list(500)
        context["revenue_this_month"] = sum(r.get("amount", 0) for r in rev_list)

        health = await db.site_health.find_one({"tenant_id": tenant_id}, {"_id": 0, "score": 1})
        context["website_health_score"] = health.get("score", 0) if health else 0

        wm = await db.working_memory.find_one({"tenant_id": tenant_id}, {"_id": 0})
        if wm:
            context["working_memory"] = {
                "summary": wm.get("summary", ""),
                "key_facts": wm.get("key_facts", [])[:5],
            }

        last_run = await db.pipeline_runs.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "completed_at": 1, "status": 1, "actions_taken": 1}
        )
        if last_run:
            context["last_pipeline_run"] = {
                "completed_at": last_run.get("completed_at", ""),
                "status": last_run.get("status", ""),
                "actions_taken": last_run.get("actions_taken", 0),
            }

        recent = db.episodic_memory.find(
            {"tenant_id": tenant_id},
            {"_id": 0, "action": 1, "result": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(7)
        context["recent_actions"] = await recent.to_list(7)

        brief = await db.morning_briefs.find_one(
            {"tenant_id": tenant_id, "date": today_start.strftime("%Y-%m-%d")},
            {"_id": 0}
        )
        if brief:
            context["todays_brief"] = {
                "summary": brief.get("summary", ""),
                "handled_count": brief.get("handled_count", 0),
                "attention_count": brief.get("attention_count", 0),
            }
            context["todays_brief_summary"] = brief.get("summary", "No brief available yet.")

        econ = await db.global_pulse_shadow.find_one({"type": "latest"}, {"_id": 0})
        if econ:
            context["economic_context"] = {
                "cad_usd": econ.get("cad_usd"),
                "boc_rate": econ.get("boc_rate"),
                "next_decision": econ.get("next_decision"),
            }

    except Exception as e:
        logger.warning(f"[ORA-CONTEXT] Error loading context for {tenant_id}: {e}")

    try:
        await db.working_memory.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "ora_context": context,
                "context_loaded_at": now.isoformat(),
            }},
            upsert=True
        )
    except Exception as e:
        logger.warning(f"[ORA-CONTEXT] Failed to cache context: {e}")

    return context


def build_ora_system_prompt(context: dict) -> str:
    """Build personalized ORA system prompt from business context."""
    biz = context.get("business_name", "your business")
    bid = context.get("business_id", "")
    brief = context.get("todays_brief_summary", "No brief available yet.")
    leads = context.get("leads_count", 0)
    approvals = context.get("pending_approvals", 0)
    outstanding = context.get("outstanding_revenue", 0)
    health = context.get("website_health_score", 0)

    return (
        f"You are ORA, the AI assistant for {biz}. "
        f"Business ID: {bid}. "
        f"You have full context of their business. "
        f"Today: {brief} "
        f"Active leads: {leads}. "
        f"Pending approvals: {approvals}. "
        f"Outstanding revenue: ${outstanding:,.0f}. "
        f"Website health: {health}/100. "
        f"Always respond as their dedicated business assistant. "
        f"Be concise. Be specific. Use their actual data in every response."
    )
