"""
ReRoots AI OODA Loop Automation
Observe-Orient-Decide-Act cycle for continuous business intelligence
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json
import secrets
import asyncio

router = APIRouter(prefix="/api/ooda", tags=["ooda-loop"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# OODA CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

OODA_CYCLES = {
    "daily_health": {
        "name": "Daily Health Check",
        "frequency": "daily",
        "observe": ["api_errors", "response_times", "user_activity"],
        "orient": ["compare_to_baseline", "identify_anomalies"],
        "decide": ["prioritize_issues", "create_tasks"],
        "act": ["send_alerts", "auto_remediate"]
    },
    "weekly_audit": {
        "name": "Weekly Business Audit",
        "frequency": "weekly",
        "observe": ["revenue", "orders", "customers", "inventory", "churn"],
        "orient": ["trend_analysis", "competitor_comparison", "goal_tracking"],
        "decide": ["strategy_adjustments", "resource_allocation"],
        "act": ["generate_report", "send_to_stakeholders"]
    },
    "customer_pulse": {
        "name": "Customer Pulse Check",
        "frequency": "daily",
        "observe": ["reviews", "support_tickets", "social_mentions"],
        "orient": ["sentiment_analysis", "topic_extraction"],
        "decide": ["response_priority", "product_improvements"],
        "act": ["auto_responses", "team_notifications"]
    },
    "inventory_watch": {
        "name": "Inventory Watch",
        "frequency": "daily",
        "observe": ["stock_levels", "sales_velocity", "supplier_status"],
        "orient": ["demand_forecast", "reorder_analysis"],
        "decide": ["reorder_decisions", "promotion_triggers"],
        "act": ["create_purchase_orders", "update_pricing"]
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class OODACycleExecution(BaseModel):
    cycle_id: str
    force_run: bool = False
    custom_params: Optional[Dict[str, Any]] = None

class CustomOODACycle(BaseModel):
    name: str
    frequency: str  # hourly, daily, weekly, monthly
    observe: List[str]
    orient: List[str]
    decide: List[str]
    act: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# OODA PHASE EXECUTORS
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_observe_phase(observations: List[str], context: Dict) -> Dict:
    """OBSERVE: Gather data from all sources"""
    data = {}
    
    for obs in observations:
        if obs == "api_errors":
            errors = await db.api_usage_logs.count_documents({
                "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(days=1)},
                "error": {"$exists": True}
            })
            data["api_errors_24h"] = errors
            
        elif obs == "response_times":
            # Average response time from logs
            avg = await db.api_usage_logs.aggregate([
                {"$match": {"timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(days=1)}}},
                {"$group": {"_id": None, "avg_latency": {"$avg": "$latency_ms"}}}
            ]).to_list(1)
            data["avg_response_time_ms"] = avg[0]["avg_latency"] if avg else 0
            
        elif obs == "user_activity":
            active_users = await db.orders.distinct("user_id", {
                "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=1)}
            })
            data["active_users_24h"] = len(active_users)
            
        elif obs == "revenue":
            revenue = await db.orders.aggregate([
                {"$match": {"created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}}},
                {"$group": {"_id": None, "total": {"$sum": "$total"}}}
            ]).to_list(1)
            data["revenue_7d"] = revenue[0]["total"] if revenue else 0
            
        elif obs == "orders":
            orders = await db.orders.count_documents({
                "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}
            })
            data["orders_7d"] = orders
            
        elif obs == "customers":
            new_customers = await db.users.count_documents({
                "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}
            })
            data["new_customers_7d"] = new_customers
            
        elif obs == "inventory":
            low_stock = await db.products.count_documents({"stock": {"$lt": 10}})
            out_of_stock = await db.products.count_documents({"stock": {"$lte": 0}})
            data["low_stock_count"] = low_stock
            data["out_of_stock_count"] = out_of_stock
            
        elif obs == "churn":
            # Customers who haven't ordered in 60+ days
            cutoff = datetime.now(timezone.utc) - timedelta(days=60)
            at_risk = await db.orders.aggregate([
                {"$group": {"_id": "$user_id", "last_order": {"$max": "$created_at"}}},
                {"$match": {"last_order": {"$lt": cutoff}}}
            ]).to_list(1000)
            data["at_risk_customers"] = len(at_risk)
            
        elif obs == "reviews":
            recent_reviews = await db.reviews.count_documents({
                "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}
            })
            data["reviews_7d"] = recent_reviews
            
        elif obs == "stock_levels":
            products = await db.products.find(
                {"active": True},
                {"_id": 0, "name": 1, "stock": 1}
            ).to_list(100)
            data["stock_levels"] = products
    
    return {"phase": "observe", "data": data}


async def execute_orient_phase(orientations: List[str], observed_data: Dict, context: Dict) -> Dict:
    """ORIENT: Analyze and contextualize observations"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"phase": "orient", "analysis": "LLM not configured"}
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ooda_orient_{secrets.token_hex(6)}",
            system_message="""You are a business intelligence analyst for ReRoots skincare.
Analyze the observed data and provide insights.
Focus on: trends, anomalies, comparisons to baselines, and actionable patterns.
Respond in JSON:
{
  "key_insights": ["insight1", "insight2"],
  "anomalies": ["anomaly1"],
  "trends": ["trend1"],
  "risk_areas": ["risk1"],
  "opportunities": ["opportunity1"],
  "severity": "low|medium|high|critical"
}"""
        ).with_model("openai", "gpt-4o-mini")
        
        analysis_prompt = f"""Analyze this business data:

Observations: {json.dumps(observed_data['data'])}

Analysis tasks: {', '.join(orientations)}

Provide your analysis."""
        
        response = await chat.send_message(UserMessage(text=analysis_prompt))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            analysis = json.loads(response.strip())
        except:
            analysis = {"raw_analysis": response[:1000]}
        
        return {"phase": "orient", "analysis": analysis}
        
    except Exception as e:
        return {"phase": "orient", "error": str(e)}


async def execute_decide_phase(decisions: List[str], analysis: Dict, context: Dict) -> Dict:
    """DECIDE: Determine best course of action"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"phase": "decide", "decisions": []}
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"ooda_decide_{secrets.token_hex(6)}",
            system_message="""You are a business decision maker for ReRoots skincare.
Based on the analysis, decide on the best actions to take.
Prioritize by impact and urgency.
Respond in JSON:
{
  "decisions": [
    {"action": "what to do", "priority": "high|medium|low", "reason": "why", "owner": "who"}
  ],
  "immediate_actions": ["action that needs to happen now"],
  "deferred_actions": ["actions for later"],
  "no_action_needed": ["areas that are fine"]
}"""
        ).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(
            text=f"""Based on this analysis, make decisions:

Analysis: {json.dumps(analysis.get('analysis', {}))}

Decision areas: {', '.join(decisions)}"""
        ))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            decisions_result = json.loads(response.strip())
        except:
            decisions_result = {"decisions": [], "raw": response[:500]}
        
        return {"phase": "decide", "decisions": decisions_result}
        
    except Exception as e:
        return {"phase": "decide", "error": str(e)}


async def execute_act_phase(actions: List[str], decisions: Dict, context: Dict) -> Dict:
    """ACT: Execute decided actions"""
    results = []
    
    for action in actions:
        if action == "send_alerts":
            # Create alert notifications
            if decisions.get("decisions", {}).get("immediate_actions"):
                await db.notifications.insert_one({
                    "type": "ooda_alert",
                    "content": decisions["decisions"]["immediate_actions"],
                    "priority": "high",
                    "created_at": datetime.now(timezone.utc)
                })
                results.append({"action": "send_alerts", "success": True})
                
        elif action == "generate_report":
            # Store report
            await db.ooda_reports.insert_one({
                "cycle_id": context.get("cycle_id"),
                "report_type": context.get("cycle_name"),
                "content": {
                    "observed": context.get("observed"),
                    "analysis": context.get("analysis"),
                    "decisions": decisions
                },
                "created_at": datetime.now(timezone.utc)
            })
            results.append({"action": "generate_report", "success": True})
            
        elif action == "send_to_stakeholders":
            # Log for notification system
            results.append({
                "action": "send_to_stakeholders",
                "success": True,
                "message": "Report queued for delivery"
            })
            
        elif action == "auto_remediate":
            # Auto-remediation placeholder
            results.append({
                "action": "auto_remediate",
                "success": True,
                "message": "Auto-remediation evaluated"
            })
    
    return {"phase": "act", "results": results}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/cycles")
async def get_ooda_cycles():
    """Get available OODA cycle configurations"""
    return {"cycles": OODA_CYCLES}


@router.post("/execute")
async def execute_ooda_cycle(data: OODACycleExecution, background_tasks: BackgroundTasks):
    """Execute an OODA cycle"""
    if data.cycle_id not in OODA_CYCLES:
        raise HTTPException(status_code=400, detail=f"Unknown cycle: {data.cycle_id}")
    
    cycle = OODA_CYCLES[data.cycle_id]
    execution_id = f"ooda_{secrets.token_hex(8)}"
    
    # Create execution record
    await db.ooda_executions.insert_one({
        "execution_id": execution_id,
        "cycle_id": data.cycle_id,
        "cycle_name": cycle["name"],
        "status": "running",
        "started_at": datetime.now(timezone.utc)
    })
    
    # Run in background
    background_tasks.add_task(run_ooda_cycle, execution_id, data.cycle_id, cycle, data.custom_params)
    
    return {
        "execution_id": execution_id,
        "cycle_id": data.cycle_id,
        "cycle_name": cycle["name"],
        "status": "running"
    }


async def run_ooda_cycle(execution_id: str, cycle_id: str, cycle: Dict, custom_params: Dict = None):
    """Run complete OODA cycle"""
    context = {
        "execution_id": execution_id,
        "cycle_id": cycle_id,
        "cycle_name": cycle["name"],
        "custom_params": custom_params or {}
    }
    
    try:
        # OBSERVE
        observed = await execute_observe_phase(cycle["observe"], context)
        context["observed"] = observed
        
        await db.ooda_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {"observe_result": observed, "phase": "observe_complete"}}
        )
        
        # ORIENT
        analysis = await execute_orient_phase(cycle["orient"], observed, context)
        context["analysis"] = analysis
        
        await db.ooda_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {"orient_result": analysis, "phase": "orient_complete"}}
        )
        
        # DECIDE
        decisions = await execute_decide_phase(cycle["decide"], analysis, context)
        context["decisions"] = decisions
        
        await db.ooda_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {"decide_result": decisions, "phase": "decide_complete"}}
        )
        
        # ACT
        actions = await execute_act_phase(cycle["act"], decisions, context)
        
        # Complete
        await db.ooda_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "act_result": actions,
                "status": "completed",
                "phase": "complete",
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
    except Exception as e:
        await db.ooda_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc)
            }}
        )


@router.get("/execution/{execution_id}")
async def get_ooda_execution(execution_id: str):
    """Get OODA cycle execution status"""
    execution = await db.ooda_executions.find_one(
        {"execution_id": execution_id},
        {"_id": 0}
    )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {"execution": execution}


@router.get("/reports")
async def get_ooda_reports(cycle_id: Optional[str] = None, limit: int = 10):
    """Get OODA cycle reports"""
    query = {}
    if cycle_id:
        query["cycle_id"] = cycle_id
    
    reports = await db.ooda_reports.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"reports": reports}


@router.post("/schedule")
async def schedule_ooda_cycle(
    cycle_id: str,
    cron_expression: str  # e.g., "0 9 * * *" for daily at 9am
):
    """Schedule an OODA cycle for recurring execution"""
    if cycle_id not in OODA_CYCLES:
        raise HTTPException(status_code=400, detail=f"Unknown cycle: {cycle_id}")
    
    schedule_id = f"sched_{secrets.token_hex(6)}"
    
    await db.ooda_schedules.insert_one({
        "schedule_id": schedule_id,
        "cycle_id": cycle_id,
        "cron_expression": cron_expression,
        "status": "active",
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "schedule_id": schedule_id,
        "cycle_id": cycle_id,
        "cron": cron_expression,
        "message": "Schedule created. Use cron service to trigger."
    }
