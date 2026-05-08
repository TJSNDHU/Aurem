"""
AUREM Intelligence Engine
=========================
Unified AI intelligence layer powering:
- RAG context from CRM, Pipeline, Analytics data
- Predictive intelligence (win probability, revenue forecast, churn)
- Lead scoring
- Generative UI component suggestions
"""

from datetime import datetime, timezone, timedelta
import json
import logging
import os

logger = logging.getLogger(__name__)

_db = None

def set_db(database):
    global _db
    _db = database

def get_db():
    return _db


async def build_rag_context(user_id: str, query: str, intent: str) -> str:
    """Build RAG context by querying real MongoDB data based on user's question"""
    db = get_db()
    if db is None:
        return ""

    context_parts = []

    try:
        # Always include basic stats
        contacts_count = await db.contacts.count_documents({})
        deals_count = await db.deals.count_documents({})

        if intent in ("sales", "general", "analytics"):
            # Pipeline deals
            deals = await db.deals.find(
                {}, {"_id": 0, "title": 1, "value": 1, "stage": 1, "status": 1, "company": 1}
            ).sort("value", -1).limit(10).to_list(10)
            if deals:
                context_parts.append(f"PIPELINE ({len(deals)} top deals):")
                for d in deals:
                    context_parts.append(
                        f"  - {d.get('title','Untitled')} | {d.get('company','-')} | ${d.get('value',0):,.0f} | Stage: {d.get('stage','-')} | {d.get('status','open')}"
                    )

        if intent in ("sales", "analytics", "general"):
            # CRM contacts
            contacts = await db.contacts.find(
                {}, {"_id": 0, "name": 1, "email": 1, "company": 1, "status": 1, "score": 1}
            ).sort("score", -1).limit(10).to_list(10)
            if contacts:
                context_parts.append(f"\nCRM CONTACTS ({contacts_count} total, top {len(contacts)}):")
                for c in contacts:
                    context_parts.append(
                        f"  - {c.get('name','-')} | {c.get('company','-')} | {c.get('email','-')} | Score: {c.get('score','-')} | {c.get('status','-')}"
                    )

        if intent in ("analytics", "general"):
            # Revenue data
            revenue = await db.revenue_events.find(
                {}, {"_id": 0, "amount": 1, "type": 1, "created_at": 1}
            ).sort("created_at", -1).limit(20).to_list(20)
            if revenue:
                total = sum(r.get("amount", 0) for r in revenue)
                context_parts.append(f"\nREVENUE (last {len(revenue)} events, total ${total:,.0f}):")
                for r in revenue[:5]:
                    context_parts.append(f"  - ${r.get('amount',0):,.0f} ({r.get('type','-')})")

        if intent in ("agent_management", "general"):
            # Agent executions
            execs = await db.agent_executions.find(
                {}, {"_id": 0, "agent_id": 1, "status": 1, "result": 1}
            ).sort("started_at", -1).limit(5).to_list(5)
            if execs:
                context_parts.append(f"\nAGENT ACTIVITY (last {len(execs)} executions):")
                for e in execs:
                    context_parts.append(f"  - {e.get('agent_id','-')}: {e.get('status','-')}")

        if intent in ("voice", "general"):
            # Voice call stats
            calls = await db.voice_calls.count_documents({})
            if calls > 0:
                context_parts.append(f"\nVOICE: {calls} total calls recorded")

        # Summary header
        header = f"LIVE BUSINESS DATA (as of {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}):"
        header += f"\n  Total Contacts: {contacts_count} | Total Deals: {deals_count}"

        return header + "\n" + "\n".join(context_parts) if context_parts else header

    except Exception as e:
        logger.error(f"[Intelligence] RAG context error: {e}")
        return f"[Data access limited: {str(e)[:50]}]"


async def predict_deal(deal_data: dict) -> dict:
    """Predict win probability and close date for a deal"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return _heuristic_deal_prediction(deal_data)

        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"predict_{secrets.token_hex(4)}",
            system_message="""You are a deal prediction AI. Analyze deal data and return ONLY valid JSON:
{"win_probability": 0.0-1.0, "predicted_close_days": integer, "risk_factors": ["factor1"], "next_action": "recommendation", "deal_health": "healthy|at_risk|cold"}"""
        ).with_model("openai", "gpt-4o-mini")

        msg = f"""Deal: {deal_data.get('title','-')}
Value: ${deal_data.get('value',0):,.0f}
Stage: {deal_data.get('stage','-')}
Company: {deal_data.get('company','-')}
Days in pipeline: {deal_data.get('days_in_pipeline', 0)}
Last activity: {deal_data.get('last_activity', 'unknown')}"""

        response = await chat.send_message(UserMessage(text=msg))
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except Exception as e:
        logger.error(f"[Intelligence] Deal prediction error: {e}")
        return _heuristic_deal_prediction(deal_data)


def _heuristic_deal_prediction(deal_data: dict) -> dict:
    """Fallback heuristic prediction"""
    stage = (deal_data.get("stage") or "").lower()
    stage_scores = {"scan": 0.15, "decision maker": 0.30, "proposal": 0.50, "contract": 0.75, "onboarding": 0.90}
    prob = stage_scores.get(stage, 0.25)
    days = deal_data.get("days_in_pipeline", 30)
    if days > 90:
        prob *= 0.7
    return {
        "win_probability": round(prob, 2),
        "predicted_close_days": max(7, 60 - int(prob * 40)),
        "risk_factors": ["Long cycle" if days > 60 else "Early stage"],
        "next_action": "Schedule follow-up" if prob < 0.5 else "Push for close",
        "deal_health": "cold" if prob < 0.3 else "at_risk" if prob < 0.6 else "healthy",
    }


async def score_lead(lead_data: dict) -> dict:
    """Score a lead from 0-100 with reasoning"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not api_key:
            return _heuristic_lead_score(lead_data)

        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"score_{secrets.token_hex(4)}",
            system_message="""Score this lead 0-100. Return ONLY valid JSON:
{"score": integer, "grade": "A|B|C|D|F", "signals": ["signal1"], "recommended_action": "action", "ideal_customer_fit": 0.0-1.0}"""
        ).with_model("openai", "gpt-4o-mini")

        msg = f"""Lead: {lead_data.get('name','-')}
Company: {lead_data.get('company','-')}
Email: {lead_data.get('email','-')}
Source: {lead_data.get('source','-')}
Website: {lead_data.get('website','-')}
Industry: {lead_data.get('industry','-')}
Company size: {lead_data.get('company_size','-')}"""

        response = await chat.send_message(UserMessage(text=msg))
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())
    except Exception as e:
        logger.error(f"[Intelligence] Lead scoring error: {e}")
        return _heuristic_lead_score(lead_data)


def _heuristic_lead_score(lead_data: dict) -> dict:
    """Fallback heuristic lead scoring"""
    score = 40
    if lead_data.get("email"):
        score += 15
    if lead_data.get("company"):
        score += 10
    if lead_data.get("website"):
        score += 10
    if lead_data.get("phone"):
        score += 10
    if lead_data.get("industry"):
        score += 5
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    return {"score": min(score, 100), "grade": grade, "signals": ["Heuristic scoring"], "recommended_action": "Enrich data", "ideal_customer_fit": score / 100}


async def forecast_revenue(months: int = 6) -> dict:
    """Forecast revenue for next N months based on historical data"""
    db = get_db()
    if db is None:
        return {"forecast": [], "confidence": 0}

    try:
        # Get historical monthly revenue
        pipeline_data = await db.deals.find(
            {"status": "won"}, {"_id": 0, "value": 1, "closed_at": 1, "created_at": 1}
        ).to_list(500)

        # Aggregate by month
        monthly = {}
        for d in pipeline_data:
            date = d.get("closed_at") or d.get("created_at")
            if date and hasattr(date, "strftime"):
                key = date.strftime("%Y-%m")
                monthly[key] = monthly.get(key, 0) + d.get("value", 0)

        # Get current pipeline value
        open_deals = await db.deals.find(
            {"status": {"$nin": ["won", "lost"]}}, {"_id": 0, "value": 1, "stage": 1}
        ).to_list(500)

        pipeline_value = sum(d.get("value", 0) for d in open_deals)
        weighted_pipeline = sum(
            d.get("value", 0) * {"scan": 0.1, "decision maker": 0.25, "proposal": 0.5, "contract": 0.75, "onboarding": 0.9}.get((d.get("stage") or "").lower(), 0.2)
            for d in open_deals
        )

        # Use LLM for intelligent forecasting if available
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if api_key and monthly:
            import secrets
            chat = LlmChat(
                api_key=api_key,
                session_id=f"forecast_{secrets.token_hex(4)}",
                system_message=f"""Forecast monthly revenue. Return ONLY valid JSON array of {months} objects:
[{{"month": "YYYY-MM", "predicted_revenue": number, "confidence": 0.0-1.0, "growth_rate": number}}]"""
            ).with_model("openai", "gpt-4o-mini")

            sorted_months = sorted(monthly.items())
            history = "\n".join(f"{m}: ${v:,.0f}" for m, v in sorted_months[-12:])
            response = await chat.send_message(UserMessage(
                text=f"Historical monthly revenue:\n{history}\n\nCurrent pipeline: ${pipeline_value:,.0f} (weighted: ${weighted_pipeline:,.0f})\n\nForecast next {months} months."
            ))
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            forecast = json.loads(response.strip())
        else:
            # Simple linear forecast
            avg = sum(monthly.values()) / max(len(monthly), 1) if monthly else pipeline_value * 0.3
            now = datetime.now(timezone.utc)
            forecast = []
            for i in range(1, months + 1):
                future = now + timedelta(days=30 * i)
                forecast.append({
                    "month": future.strftime("%Y-%m"),
                    "predicted_revenue": round(avg * (1 + 0.03 * i), 2),
                    "confidence": max(0.4, 0.9 - 0.08 * i),
                    "growth_rate": 0.03,
                })

        return {
            "forecast": forecast,
            "historical": dict(sorted(monthly.items())[-6:]) if monthly else {},
            "current_pipeline": pipeline_value,
            "weighted_pipeline": round(weighted_pipeline, 2),
            "methodology": "ai_enhanced" if api_key and monthly else "linear_projection",
        }

    except Exception as e:
        logger.error(f"[Intelligence] Revenue forecast error: {e}")
        return {"forecast": [], "confidence": 0, "error": str(e)}


def suggest_generative_ui(intent: str, data: dict) -> list:
    """Suggest Generative UI components based on intent and data"""
    components = []

    if intent == "analytics" or intent == "sales":
        if "deals" in data:
            components.append({
                "type": "bar_chart",
                "title": "Pipeline by Stage",
                "data_key": "deals_by_stage",
            })
        if "revenue" in data:
            components.append({
                "type": "line_chart",
                "title": "Revenue Trend",
                "data_key": "revenue_trend",
            })
        if "forecast" in data:
            components.append({
                "type": "line_chart",
                "title": "Revenue Forecast",
                "data_key": "forecast",
            })

    if intent == "agent_management":
        components.append({
            "type": "metric_card",
            "title": "Agent Status",
            "data_key": "agent_stats",
        })

    return components
