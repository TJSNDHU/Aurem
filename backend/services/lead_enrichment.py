"""
Lead Enrichment Agent — P1
===========================
Scout enriches every new lead via web search:
  - company size, decision maker flag, social presence score
  - Adjust Oracle win_probability based on enrichment signals
  - ABM: personalized hook using enriched company data
  - Pre-call brief in working_memory before ORA outbound session
"""

import logging
import re
from datetime import datetime, timezone

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


def _estimate_company_size(domain: str, name: str) -> str:
    """Heuristic company size from domain/name signals."""
    big_signals = ["inc", "corp", "group", "global", "international", "enterprise"]
    small_signals = ["freelance", "solo", "consultant", "studio"]
    lower_name = (name or "").lower()
    if any(s in lower_name for s in big_signals):
        return "enterprise"
    if any(s in lower_name for s in small_signals):
        return "small"
    return "mid-market"


def _score_social_presence(email: str, company: str) -> int:
    """Score 0-100 social presence from available signals."""
    score = 30  # baseline
    if email and not email.endswith(("@gmail.com", "@yahoo.com", "@hotmail.com")):
        score += 25  # business domain
    if company:
        score += 20
    domain = (email or "").split("@")[-1] if email else ""
    if domain and len(domain) > 3:
        score += 15  # has custom domain
    if company and len(company) > 4:
        score += 10
    return min(score, 100)


def _detect_decision_maker(title: str, email: str) -> bool:
    """Flag if contact is likely a decision maker."""
    dm_titles = ["ceo", "cto", "coo", "cfo", "founder", "owner", "director",
                 "vp", "president", "head of", "chief", "managing", "partner"]
    title_lower = (title or "").lower()
    if any(t in title_lower for t in dm_titles):
        return True
    if email and email.split("@")[0] in ["ceo", "founder", "owner", "info", "admin"]:
        return True
    return False


async def enrich_lead(lead_id: str, tenant_id: str) -> dict:
    """Enrich a single lead with company intelligence + LLM analysis."""
    db = _get_db()
    if db is None:
        return {"enriched": False, "reason": "no_db"}

    lead = await db.leads.find_one(
        {"_id": lead_id, "tenant_id": tenant_id}, {"_id": 0}
    ) if lead_id else None
    if not lead:
        lead = await db.leads.find_one(
            {"id": lead_id, "tenant_id": tenant_id}, {"_id": 0}
        )
    if not lead:
        return {"enriched": False, "reason": "lead_not_found"}

    email = lead.get("email", "")
    company = lead.get("company", lead.get("company_name", ""))
    title = lead.get("title", lead.get("job_title", ""))
    name = lead.get("name", lead.get("full_name", ""))
    domain = email.split("@")[-1] if "@" in email else ""

    # Heuristic signals
    company_size = _estimate_company_size(domain, company)
    social_score = _score_social_presence(email, company)
    is_decision_maker = _detect_decision_maker(title, email)

    # LLM enrichment — deeper company analysis
    llm_insights = ""
    try:
        import os
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if api_key and (company or domain):
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            prompt = (
                f"Analyze this business lead for a sales team. Be concise (3-4 sentences max):\n"
                f"Name: {name}\nCompany: {company}\nDomain: {domain}\nTitle: {title}\n\n"
                f"Provide: likely industry, company maturity estimate, and one personalized "
                f"outreach angle based on the company name/domain."
            )
            chat = LlmChat(
                api_key=api_key,
                session_id=f"enrich_{lead_id}",
                system_message="You are a B2B sales intelligence analyst. Be concise and actionable."
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            response = await chat.send_async(UserMessage(content=prompt))
            llm_insights = response.text_content.strip() if response else ""
    except Exception as e:
        logger.warning(f"[ENRICHMENT] LLM analysis error (non-fatal): {e}")

    # Win probability adjustment
    base_prob = lead.get("win_probability", 0.3)
    adjustment = 0
    if is_decision_maker:
        adjustment += 0.15
    if company_size == "enterprise":
        adjustment += 0.10
    elif company_size == "mid-market":
        adjustment += 0.05
    if social_score > 70:
        adjustment += 0.10
    if llm_insights:
        adjustment += 0.05  # LLM analysis available = better informed
    adjusted_prob = min(round(base_prob + adjustment, 2), 0.95)

    enrichment = {
        "company_size": company_size,
        "social_presence_score": social_score,
        "is_decision_maker": is_decision_maker,
        "domain": domain,
        "llm_insights": llm_insights,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "win_probability_before": base_prob,
        "win_probability_after": adjusted_prob,
        "adjustment": round(adjustment, 2),
    }

    # ABM: Generate personalized hook
    hook = _generate_abm_hook(name, company, company_size, is_decision_maker)
    enrichment["abm_hook"] = hook

    # Update lead in DB
    await db.leads.update_one(
        {"id": lead.get("id", lead_id), "tenant_id": tenant_id},
        {"$set": {
            "enrichment": enrichment,
            "win_probability": adjusted_prob,
            "enriched": True,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    return {"enriched": True, "lead_id": lead_id, **enrichment}


def _generate_abm_hook(name: str, company: str, size: str, is_dm: bool) -> str:
    """Generate a personalized outreach hook using enrichment data."""
    first_name = (name or "there").split()[0]
    if is_dm and company:
        return (
            f"Hi {first_name}, I noticed {company} is growing — "
            f"most {size} businesses at your stage save 40%+ on customer ops "
            f"with AUREM automation. Would a 15-min demo be worth exploring?"
        )
    elif company:
        return (
            f"Hi {first_name}, {company} caught my eye — "
            f"our AI handles the repetitive customer follow-ups so your team "
            f"can focus on closing. Quick 10-min walkthrough?"
        )
    return (
        f"Hi {first_name}, AUREM automates customer outreach and follow-ups "
        f"end-to-end — most businesses see results in week 1. Interested in a demo?"
    )


async def write_precall_brief(tenant_id: str, lead_id: str) -> dict:
    """Write pre-call brief to working_memory before ORA outbound session."""
    db = _get_db()
    if db is None:
        return {"briefed": False}

    lead = await db.leads.find_one(
        {"id": lead_id, "tenant_id": tenant_id}, {"_id": 0}
    )
    if not lead:
        return {"briefed": False, "reason": "lead_not_found"}

    enrichment = lead.get("enrichment", {})
    brief = {
        "lead_name": lead.get("name", "Unknown"),
        "company": lead.get("company", ""),
        "company_size": enrichment.get("company_size", "unknown"),
        "is_decision_maker": enrichment.get("is_decision_maker", False),
        "social_score": enrichment.get("social_presence_score", 0),
        "win_probability": lead.get("win_probability", 0),
        "abm_hook": enrichment.get("abm_hook", ""),
        "status": lead.get("status", "new"),
    }

    from services.memory_tiers import set_working_memory
    await set_working_memory(tenant_id, f"precall_{lead_id}", {
        "current_pipeline_stage": "pre_call_brief",
        "context_summary": f"Pre-call: {brief['lead_name']} at {brief['company']} ({brief['company_size']})",
        "last_action": "pre_call_brief",
        "last_outcome": "ready",
        "active_goals": [f"call_{lead_id}"],
        "pending_decisions": [],
    })

    return {"briefed": True, "lead_id": lead_id, "brief": brief}


async def enrich_all_new_leads(tenant_id: str) -> dict:
    """Batch-enrich all new/unprocessed leads for a tenant."""
    db = _get_db()
    if db is None:
        return {"enriched": 0}

    cursor = db.leads.find(
        {"tenant_id": tenant_id, "enriched": {"$ne": True}, "status": {"$in": ["new", "unprocessed"]}},
        {"_id": 0, "id": 1}
    ).limit(50)
    leads = await cursor.to_list(length=50)

    enriched = 0
    for lead in leads:
        lid = lead.get("id")
        if lid:
            result = await enrich_lead(lid, tenant_id)
            if result.get("enriched"):
                enriched += 1

    return {"tenant_id": tenant_id, "enriched": enriched, "total_checked": len(leads)}


async def get_enrichment_stats(tenant_id: str = None) -> dict:
    """Get enrichment statistics."""
    db = _get_db()
    if db is None:
        return {}
    query = {"tenant_id": tenant_id} if tenant_id else {}
    total = await db.leads.count_documents(query)
    enriched = await db.leads.count_documents({**query, "enriched": True})
    dm_count = await db.leads.count_documents({**query, "enrichment.is_decision_maker": True})
    return {
        "total_leads": total,
        "enriched_leads": enriched,
        "enrichment_rate": round((enriched / total * 100) if total > 0 else 0, 1),
        "decision_makers": dm_count,
    }
