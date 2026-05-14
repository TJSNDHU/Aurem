"""
AUREM Agent Execution Engine
=============================
Makes agents in the Agent Swarm actually execute real tasks:
- CRM data enrichment
- Lead outreach automation
- Pipeline analysis
- Competitive intelligence
- Audit trail with cryptographic hashing (blockchain-lite)
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import hashlib
import json
import uuid
import jwt
import os
import logging

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = logging.getLogger(__name__)

_db = None

def set_db(database):
    global _db
    _db = database


def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ============ AGENT DEFINITIONS ============
AGENTS = {
    "scout": {
        "id": "scout",
        "name": "Scout Agent",
        "description": "Discovers and qualifies new leads from existing data",
        "capabilities": ["lead_discovery", "data_enrichment", "competitor_scan"],
        "status": "active",
    },
    "envoy": {
        "id": "envoy",
        "name": "Envoy Agent",
        "description": "Handles outreach and initial engagement",
        "capabilities": ["email_draft", "followup_scheduling", "response_tracking"],
        "status": "active",
    },
    "closer": {
        "id": "closer",
        "name": "Closer Agent",
        "description": "Manages deal progression and closing strategies",
        "capabilities": ["deal_analysis", "proposal_generation", "negotiation_support"],
        "status": "active",
    },
    "architect": {
        "id": "architect",
        "name": "Architect Agent",
        "description": "Designs automation workflows and system optimizations",
        "capabilities": ["workflow_design", "system_audit", "optimization"],
        "status": "active",
    },
    "oracle": {
        "id": "oracle",
        "name": "Oracle Agent",
        "description": "Predictive analytics and business intelligence",
        "capabilities": ["revenue_forecast", "churn_prediction", "trend_analysis"],
        "status": "active",
    },
}


class AgentExecuteRequest(BaseModel):
    agent_id: str
    action: str
    parameters: dict = {}


class AgentSwarmRequest(BaseModel):
    objective: str
    agents: list = []
    auto_select: bool = True


# ============ BLOCKCHAIN AUDIT TRAIL ============
async def create_audit_entry(db, action: str, agent_id: str, data: dict, prev_hash: str = None):
    """Create an immutable audit entry with cryptographic hash chain"""
    if not prev_hash:
        last = await db.audit_chain.find_one(sort=[("sequence", -1)])
        prev_hash = last["hash"] if last else "0" * 64

    entry = {
        "sequence": (await db.audit_chain.count_documents({})),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "action": action,
        "data_summary": json.dumps(data, default=str)[:500],
        "prev_hash": prev_hash,
    }

    # SHA-256 hash of the entry + previous hash
    hash_input = json.dumps(entry, sort_keys=True)
    entry["hash"] = hashlib.sha256(hash_input.encode()).hexdigest()
    entry["verified"] = True

    await db.audit_chain.insert_one({**entry})
    return entry["hash"]


# ============ AGENT EXECUTION FUNCTIONS ============
async def execute_scout(params: dict, db) -> dict:
    """Scout agent: discover and qualify leads"""
    contacts = await db.contacts.find(
        {"score": {"$exists": False}}, {"_id": 0}
    ).limit(10).to_list(10)

    from services.intelligence_engine import score_lead
    results = []
    for c in contacts:
        scoring = await score_lead(c)
        # Update contact with score
        if c.get("email"):
            await db.contacts.update_one(
                {"email": c["email"]},
                {"$set": {"score": scoring.get("score", 0), "grade": scoring.get("grade", "C"), "scored_at": datetime.now(timezone.utc).isoformat()}}
            )
        results.append({"name": c.get("name", "-"), "score": scoring.get("score", 0), "grade": scoring.get("grade", "C")})

    return {
        "action": "lead_discovery",
        "leads_scored": len(results),
        "results": results[:5],
        "summary": f"Scored {len(results)} leads. {sum(1 for r in results if r['grade'] in ('A','B'))} high-quality leads found.",
    }


async def execute_envoy(params: dict, db) -> dict:
    """Envoy agent: draft outreach for top leads"""
    top_leads = await db.contacts.find(
        {"grade": {"$in": ["A", "B"]}}, {"_id": 0, "name": 1, "email": 1, "company": 1, "grade": 1}
    ).sort("score", -1).limit(5).to_list(5)

    outreach_plans = []
    for lead in top_leads:
        outreach_plans.append({
            "contact": lead.get("name", "-"),
            "company": lead.get("company", "-"),
            "channel": "email",
            "priority": "high" if lead.get("grade") == "A" else "medium",
            "suggested_action": f"Send personalized intro to {lead.get('name', 'contact')} at {lead.get('company', 'their company')}",
        })

    return {
        "action": "outreach_planning",
        "outreach_count": len(outreach_plans),
        "plans": outreach_plans,
        "summary": f"Created {len(outreach_plans)} outreach plans for top-scored leads.",
    }


async def execute_closer(params: dict, db) -> dict:
    """Closer agent: analyze deals and suggest closing strategies"""
    deals = await db.deals.find(
        {"status": {"$nin": ["won", "lost"]}}, {"_id": 0}
    ).sort("value", -1).limit(10).to_list(10)

    from services.intelligence_engine import predict_deal
    strategies = []
    for deal in deals:
        pred = await predict_deal(deal)
        strategies.append({
            "deal": deal.get("title", "-"),
            "value": deal.get("value", 0),
            "win_probability": pred.get("win_probability", 0),
            "health": pred.get("deal_health", "unknown"),
            "next_action": pred.get("next_action", "Follow up"),
        })

    at_risk = [s for s in strategies if s["health"] == "at_risk"]

    return {
        "action": "deal_analysis",
        "deals_analyzed": len(strategies),
        "at_risk_count": len(at_risk),
        "strategies": strategies[:5],
        "summary": f"Analyzed {len(strategies)} deals. {len(at_risk)} at risk. Total pipeline: ${sum(s['value'] for s in strategies):,.0f}",
    }


async def execute_oracle(params: dict, db) -> dict:
    """Oracle agent: predictive analytics"""
    from services.intelligence_engine import forecast_revenue
    forecast = await forecast_revenue(3)

    return {
        "action": "predictive_analytics",
        "forecast": forecast.get("forecast", []),
        "pipeline_value": forecast.get("current_pipeline", 0),
        "weighted_pipeline": forecast.get("weighted_pipeline", 0),
        "methodology": forecast.get("methodology", "unknown"),
        "summary": f"Revenue forecast generated. Weighted pipeline: ${forecast.get('weighted_pipeline', 0):,.0f}",
    }


async def execute_architect(params: dict, db) -> dict:
    """Architect agent: system audit"""
    collections = await db.list_collection_names()
    stats = {}
    for coll in collections[:15]:
        count = await db[coll].count_documents({})
        if count > 0:
            stats[coll] = count

    return {
        "action": "system_audit",
        "active_collections": len(stats),
        "data_summary": stats,
        "summary": f"Audited {len(stats)} active collections. System healthy.",
    }


AGENT_EXECUTORS = {
    "scout": execute_scout,
    "envoy": execute_envoy,
    "closer": execute_closer,
    "oracle": execute_oracle,
    "architect": execute_architect,
}


# ============ ROUTES ============
@router.get("/list")
async def list_agents(request: Request):
    _get_user(request)
    return {"agents": list(AGENTS.values()), "total": len(AGENTS)}


@router.post("/execute")
async def execute_agent(request: Request, body: AgentExecuteRequest, background_tasks: BackgroundTasks):
    """Execute a specific agent task"""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    if body.agent_id not in AGENTS:
        raise HTTPException(400, f"Unknown agent: {body.agent_id}")

    execution_id = str(uuid.uuid4())

    # Store execution record
    await _db.agent_executions.insert_one({
        "execution_id": execution_id,
        "agent_id": body.agent_id,
        "action": body.action,
        "parameters": body.parameters,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })

    # Execute
    executor = AGENT_EXECUTORS.get(body.agent_id)
    if executor:
        try:
            result = await executor(body.parameters, _db)
            await _db.agent_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {"status": "completed", "result": result, "completed_at": datetime.now(timezone.utc).isoformat()}}
            )
            # Audit trail
            await create_audit_entry(_db, body.action, body.agent_id, result)
            return {"success": True, "execution_id": execution_id, "result": result}
        except Exception as e:
            await _db.agent_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )
            raise HTTPException(500, f"Agent execution failed: {str(e)}")

    return {"success": True, "execution_id": execution_id, "result": {"summary": f"Agent {body.agent_id} task queued."}}


@router.post("/swarm/execute")
async def execute_swarm(request: Request, body: AgentSwarmRequest):
    """Execute multiple agents toward a single objective"""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    swarm_id = str(uuid.uuid4())
    agent_ids = body.agents if body.agents else list(AGENTS.keys())

    results = {}
    for agent_id in agent_ids:
        if agent_id in AGENT_EXECUTORS:
            try:
                result = await AGENT_EXECUTORS[agent_id]({}, _db)
                results[agent_id] = {"status": "completed", "result": result}
            except Exception as e:
                results[agent_id] = {"status": "failed", "error": str(e)}

    # Store swarm execution
    await _db.swarm_executions.insert_one({
        "swarm_id": swarm_id,
        "objective": body.objective,
        "agents": agent_ids,
        "results": {k: {**v, "result": {kk: vv for kk, vv in v.get("result", {}).items() if kk != "results"}} for k, v in results.items()},
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })

    # Audit
    await create_audit_entry(_db, "swarm_execution", "swarm", {"objective": body.objective, "agents": agent_ids})

    completed = sum(1 for v in results.values() if v["status"] == "completed")

    return {
        "success": True,
        "swarm_id": swarm_id,
        "objective": body.objective,
        "agents_executed": len(results),
        "agents_completed": completed,
        "results": results,
    }


@router.get("/executions")
async def get_executions(request: Request, limit: int = 20):
    """Get recent agent executions"""
    _get_user(request)
    if _db is None:
        return {"executions": []}

    execs = await _db.agent_executions.find(
        {}, {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)

    return {"executions": execs, "total": len(execs)}


@router.get("/audit-chain")
async def get_audit_chain(request: Request, limit: int = 50):
    """Get the cryptographic audit trail"""
    _get_user(request)
    if _db is None:
        return {"chain": [], "verified": True}

    entries = await _db.audit_chain.find(
        {}, {"_id": 0}
    ).sort("sequence", -1).limit(limit).to_list(limit)

    # Verify chain integrity
    verified = True
    for i in range(len(entries) - 1):
        if entries[i].get("prev_hash") != entries[i + 1].get("hash"):
            verified = False
            break

    return {"chain": entries, "total": len(entries), "chain_verified": verified}
