"""
ReRoots AI A2A Self-Learning Interceptor
Agent-to-Agent communication system for continuous skill upgrades
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json
import asyncio
import secrets

router = APIRouter(prefix="/api/a2a-learning", tags=["a2a-learning"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

REGISTERED_AGENTS = {
    "skin_analysis_agent": {
        "name": "Skin Analysis AI",
        "description": "Analyzes skin conditions from photos",
        "skills": ["image_analysis", "skin_condition_detection", "product_recommendation"],
        "version": "1.0.0",
        "endpoint": "/api/skin-analysis/analyze"
    },
    "sentiment_agent": {
        "name": "Sentiment Analysis AI",
        "description": "Analyzes customer sentiment from text",
        "skills": ["text_analysis", "emotion_detection", "trend_identification"],
        "version": "1.0.0",
        "endpoint": "/api/sentiment/analyze"
    },
    "product_ai_agent": {
        "name": "Product Description AI",
        "description": "Generates product descriptions and marketing copy",
        "skills": ["copywriting", "seo_optimization", "brand_voice"],
        "version": "1.0.0",
        "endpoint": "/api/product-ai/generate/description"
    },
    "churn_prediction_agent": {
        "name": "Churn Prediction AI",
        "description": "Predicts customer churn probability",
        "skills": ["predictive_analytics", "customer_behavior", "retention_strategy"],
        "version": "1.0.0",
        "endpoint": "/api/churn/predict"
    },
    "inventory_agent": {
        "name": "Inventory AI",
        "description": "Predicts inventory needs and optimizes stock",
        "skills": ["demand_forecasting", "stock_optimization", "trend_analysis"],
        "version": "1.0.0",
        "endpoint": "/api/inventory-ai/predict"
    },
    "weather_skincare_agent": {
        "name": "Weather Skincare AI",
        "description": "Recommends products based on weather conditions",
        "skills": ["weather_analysis", "seasonal_recommendations", "climate_adaptation"],
        "version": "1.0.0",
        "endpoint": "/api/weather-skincare/analyze"
    },
    "translation_agent": {
        "name": "Translation AI",
        "description": "Translates content to multiple languages",
        "skills": ["multi_language", "localization", "cultural_adaptation"],
        "version": "1.0.0",
        "endpoint": "/api/translate/text"
    },
    "document_scanner_agent": {
        "name": "Document Scanner AI",
        "description": "Extracts data from documents and images",
        "skills": ["ocr", "data_extraction", "document_classification"],
        "version": "1.0.0",
        "endpoint": "/api/document-scanner/scan"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentMessage(BaseModel):
    from_agent: str
    to_agent: str
    message_type: str  # skill_share, knowledge_update, error_report, optimization
    payload: Dict[str, Any]
    priority: str = "normal"  # low, normal, high, critical

class LearningSession(BaseModel):
    topic: str
    agents: List[str]
    objective: str

class SkillUpgrade(BaseModel):
    agent_id: str
    skill_name: str
    improvement_data: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# A2A COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/agents")
async def get_registered_agents():
    """Get all registered AI agents"""
    return {"agents": REGISTERED_AGENTS}


@router.post("/message")
async def send_agent_message(data: AgentMessage):
    """Send message between agents"""
    if data.from_agent not in REGISTERED_AGENTS:
        raise HTTPException(status_code=400, detail=f"Unknown sender agent: {data.from_agent}")
    if data.to_agent not in REGISTERED_AGENTS and data.to_agent != "broadcast":
        raise HTTPException(status_code=400, detail=f"Unknown recipient agent: {data.to_agent}")
    
    message_id = f"msg_{secrets.token_hex(8)}"
    
    message_record = {
        "message_id": message_id,
        "from_agent": data.from_agent,
        "to_agent": data.to_agent,
        "message_type": data.message_type,
        "payload": data.payload,
        "priority": data.priority,
        "status": "delivered",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.a2a_messages.insert_one(message_record)
    
    # Process message based on type
    if data.message_type == "skill_share":
        await process_skill_share(data)
    elif data.message_type == "knowledge_update":
        await process_knowledge_update(data)
    elif data.message_type == "error_report":
        await process_error_report(data)
    elif data.message_type == "optimization":
        await process_optimization(data)
    
    return {
        "message_id": message_id,
        "status": "delivered",
        "from": data.from_agent,
        "to": data.to_agent
    }


async def process_skill_share(message: AgentMessage):
    """Process skill sharing between agents"""
    await db.agent_skills.update_one(
        {"agent_id": message.to_agent, "skill_name": message.payload.get("skill_name")},
        {"$set": {
            "learned_from": message.from_agent,
            "skill_data": message.payload.get("skill_data"),
            "learned_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )


async def process_knowledge_update(message: AgentMessage):
    """Process knowledge base update"""
    await db.agent_knowledge.insert_one({
        "agent_id": message.to_agent,
        "knowledge_type": message.payload.get("type"),
        "content": message.payload.get("content"),
        "source_agent": message.from_agent,
        "added_at": datetime.now(timezone.utc)
    })


async def process_error_report(message: AgentMessage):
    """Process error report and learn from failures"""
    await db.agent_errors.insert_one({
        "agent_id": message.from_agent,
        "error_type": message.payload.get("error_type"),
        "context": message.payload.get("context"),
        "resolution": message.payload.get("resolution"),
        "reported_at": datetime.now(timezone.utc)
    })


async def process_optimization(message: AgentMessage):
    """Process optimization suggestions"""
    await db.agent_optimizations.insert_one({
        "target_agent": message.to_agent,
        "suggestion_from": message.from_agent,
        "optimization_type": message.payload.get("type"),
        "suggestion": message.payload.get("suggestion"),
        "expected_improvement": message.payload.get("expected_improvement"),
        "created_at": datetime.now(timezone.utc)
    })


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY LEARNING & SKILL UPGRADES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/daily-learning")
async def trigger_daily_learning(background_tasks: BackgroundTasks):
    """Trigger daily learning session for all agents"""
    session_id = f"learn_{secrets.token_hex(8)}"
    
    # Create learning session
    session = {
        "session_id": session_id,
        "type": "daily_learning",
        "status": "started",
        "agents_involved": list(REGISTERED_AGENTS.keys()),
        "started_at": datetime.now(timezone.utc)
    }
    
    await db.learning_sessions.insert_one(session)
    
    # Start background learning
    background_tasks.add_task(run_daily_learning, session_id)
    
    return {
        "session_id": session_id,
        "status": "Learning session started",
        "agents": list(REGISTERED_AGENTS.keys())
    }


async def run_daily_learning(session_id: str):
    """Background task for daily learning"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            await update_session_status(session_id, "failed", "No API key")
            return
        
        learnings = []
        
        # Step 1: Analyze recent performance data
        performance_data = await analyze_agent_performance()
        
        # Step 2: AI-powered learning session
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message="""You are the AI Learning Orchestrator for a skincare AI platform.
Analyze agent performance data and generate improvement recommendations.
Focus on:
1. Identifying patterns in successful interactions
2. Learning from errors and edge cases
3. Cross-pollinating skills between agents
4. Optimizing response quality and accuracy

Respond in JSON:
{
  "insights": [{"agent": "agent_id", "insight": "string", "priority": "high|medium|low"}],
  "skill_upgrades": [{"agent": "agent_id", "skill": "string", "improvement": "string"}],
  "cross_learnings": [{"from": "agent_id", "to": "agent_id", "knowledge": "string"}],
  "overall_health": "score 1-100"
}"""
        ).with_model("openai", "gpt-5.2")
        
        response = await chat.send_message(UserMessage(
            text=f"""Analyze performance and generate learning recommendations:
            
Performance Data:
{json.dumps(performance_data, default=str)}

Recent Errors:
{json.dumps(await get_recent_errors(), default=str)}

Usage Patterns:
{json.dumps(await get_usage_patterns(), default=str)}"""
        ))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            learning_result = json.loads(response.strip())
        except:
            learning_result = {"insights": [], "skill_upgrades": [], "overall_health": 70}
        
        # Step 3: Apply learnings
        for upgrade in learning_result.get("skill_upgrades", []):
            await apply_skill_upgrade(
                upgrade.get("agent"),
                upgrade.get("skill"),
                upgrade.get("improvement")
            )
        
        for cross in learning_result.get("cross_learnings", []):
            await db.agent_knowledge.insert_one({
                "agent_id": cross.get("to"),
                "knowledge_type": "cross_learning",
                "content": cross.get("knowledge"),
                "source_agent": cross.get("from"),
                "added_at": datetime.now(timezone.utc)
            })
        
        # Step 4: Update session
        await db.learning_sessions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "result": learning_result,
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
        # Step 5: Broadcast learning summary
        await broadcast_learning_summary(learning_result)
        
    except Exception as e:
        await update_session_status(session_id, "failed", str(e))


async def analyze_agent_performance() -> Dict:
    """Analyze recent agent performance"""
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    performance = {}
    
    # Analyze each agent's performance
    for agent_id in REGISTERED_AGENTS.keys():
        # Get usage stats
        usage = await db.api_usage_logs.count_documents({
            "feature": agent_id.replace("_agent", ""),
            "timestamp": {"$gte": yesterday}
        })
        
        # Get error count
        errors = await db.agent_errors.count_documents({
            "agent_id": agent_id,
            "reported_at": {"$gte": yesterday}
        })
        
        # Get success rate
        success_rate = max(0, 100 - (errors / max(usage, 1) * 100))
        
        performance[agent_id] = {
            "total_calls": usage,
            "error_count": errors,
            "success_rate": round(success_rate, 2)
        }
    
    return performance


async def get_recent_errors() -> List[Dict]:
    """Get recent errors for learning"""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    errors = await db.agent_errors.find(
        {"reported_at": {"$gte": yesterday}},
        {"_id": 0}
    ).limit(20).to_list(20)
    
    return errors


async def get_usage_patterns() -> Dict:
    """Get usage patterns for analysis"""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    # Hourly usage distribution
    hourly = await db.api_usage_logs.aggregate([
        {"$match": {"timestamp": {"$gte": week_ago}}},
        {"$group": {
            "_id": {"$hour": "$timestamp"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]).to_list(24)
    
    return {
        "hourly_distribution": {h["_id"]: h["count"] for h in hourly},
        "peak_hours": sorted([h["_id"] for h in hourly], key=lambda x: next((item["count"] for item in hourly if item["_id"] == x), 0), reverse=True)[:3]
    }


async def apply_skill_upgrade(agent_id: str, skill: str, improvement: str):
    """Apply skill upgrade to agent"""
    await db.agent_skills.update_one(
        {"agent_id": agent_id, "skill_name": skill},
        {"$set": {
            "last_upgrade": datetime.now(timezone.utc),
            "improvement_applied": improvement,
            "version": f"upgraded_{datetime.now().strftime('%Y%m%d')}"
        }},
        upsert=True
    )


async def broadcast_learning_summary(result: Dict):
    """Broadcast learning summary to all agents"""
    await db.a2a_messages.insert_one({
        "message_id": f"broadcast_{secrets.token_hex(6)}",
        "from_agent": "learning_orchestrator",
        "to_agent": "broadcast",
        "message_type": "learning_summary",
        "payload": result,
        "priority": "normal",
        "created_at": datetime.now(timezone.utc)
    })


async def update_session_status(session_id: str, status: str, error: str = None):
    """Update learning session status"""
    update = {"status": status, "updated_at": datetime.now(timezone.utc)}
    if error:
        update["error"] = error
    
    await db.learning_sessions.update_one(
        {"session_id": session_id},
        {"$set": update}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/skills/{agent_id}")
async def get_agent_skills(agent_id: str):
    """Get skills for a specific agent"""
    if agent_id not in REGISTERED_AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Base skills
    base_skills = REGISTERED_AGENTS[agent_id]["skills"]
    
    # Learned skills
    learned = await db.agent_skills.find(
        {"agent_id": agent_id},
        {"_id": 0}
    ).to_list(50)
    
    return {
        "agent_id": agent_id,
        "agent_name": REGISTERED_AGENTS[agent_id]["name"],
        "base_skills": base_skills,
        "learned_skills": learned,
        "total_skills": len(base_skills) + len(learned)
    }


@router.post("/skills/upgrade")
async def manual_skill_upgrade(data: SkillUpgrade):
    """Manually upgrade an agent's skill"""
    if data.agent_id not in REGISTERED_AGENTS:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.agent_skills.update_one(
        {"agent_id": data.agent_id, "skill_name": data.skill_name},
        {"$set": {
            "improvement_data": data.improvement_data,
            "upgraded_at": datetime.now(timezone.utc),
            "source": "manual"
        }},
        upsert=True
    )
    
    return {"success": True, "message": f"Skill '{data.skill_name}' upgraded for {data.agent_id}"}


# ═══════════════════════════════════════════════════════════════════════════════
# LEARNING HISTORY & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/history")
async def get_learning_history(limit: int = 20):
    """Get learning session history"""
    sessions = await db.learning_sessions.find(
        {},
        {"_id": 0}
    ).sort("started_at", -1).limit(limit).to_list(limit)
    
    return {"sessions": sessions}


@router.get("/analytics")
async def get_learning_analytics():
    """Get analytics about agent learning"""
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    
    # Total learning sessions
    total_sessions = await db.learning_sessions.count_documents({})
    sessions_this_month = await db.learning_sessions.count_documents({
        "started_at": {"$gte": month_ago}
    })
    
    # Total skills learned
    total_skills = await db.agent_skills.count_documents({})
    
    # Messages exchanged
    messages = await db.a2a_messages.count_documents({})
    
    # Agent health scores
    agent_health = {}
    for agent_id in REGISTERED_AGENTS.keys():
        skills = await db.agent_skills.count_documents({"agent_id": agent_id})
        errors = await db.agent_errors.count_documents({
            "agent_id": agent_id,
            "reported_at": {"$gte": month_ago}
        })
        agent_health[agent_id] = {
            "skills_learned": skills,
            "errors_this_month": errors,
            "health_score": max(0, 100 - errors * 5)
        }
    
    return {
        "total_learning_sessions": total_sessions,
        "sessions_this_month": sessions_this_month,
        "total_skills_learned": total_skills,
        "a2a_messages_exchanged": messages,
        "agent_health": agent_health,
        "system_health": sum(a["health_score"] for a in agent_health.values()) / len(agent_health) if agent_health else 100
    }


@router.get("/knowledge-base")
async def get_knowledge_base(agent_id: Optional[str] = None):
    """Get accumulated knowledge base"""
    query = {}
    if agent_id:
        query["agent_id"] = agent_id
    
    knowledge = await db.agent_knowledge.find(
        query,
        {"_id": 0}
    ).sort("added_at", -1).limit(100).to_list(100)
    
    return {"knowledge": knowledge}
