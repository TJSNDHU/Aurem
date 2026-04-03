"""
ReRoots AI CrewAI-style Multi-Agent Crews
Role-based agent teams for complex multi-step tasks
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json
import secrets
import asyncio

router = APIRouter(prefix="/api/crews", tags=["agent-crews"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT ROLES
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_ROLES = {
    "researcher": {
        "name": "Research Analyst",
        "description": "Gathers and analyzes information from multiple sources",
        "skills": ["data_gathering", "analysis", "summarization"],
        "tools": ["web_search", "document_scanner", "sentiment_analysis"]
    },
    "strategist": {
        "name": "Strategy Planner",
        "description": "Creates strategic plans and recommendations",
        "skills": ["planning", "decision_making", "optimization"],
        "tools": ["churn_prediction", "inventory_ai", "analytics"]
    },
    "writer": {
        "name": "Content Writer",
        "description": "Creates marketing copy and communications",
        "skills": ["copywriting", "translation", "personalization"],
        "tools": ["product_ai", "translation", "email_ai"]
    },
    "executor": {
        "name": "Action Executor",
        "description": "Executes actions and sends communications",
        "skills": ["automation", "communication", "follow_up"],
        "tools": ["sms", "whatsapp", "email", "browser_agent"]
    },
    "analyst": {
        "name": "Data Analyst",
        "description": "Analyzes data and creates reports",
        "skills": ["data_analysis", "visualization", "reporting"],
        "tools": ["sentiment_analysis", "churn_prediction", "inventory_ai"]
    },
    "auditor": {
        "name": "Quality Auditor",
        "description": "Reviews work and ensures quality standards",
        "skills": ["quality_check", "compliance", "validation"],
        "tools": ["document_scanner", "browser_agent"]
    }
}


# Pre-defined crew templates
CREW_TEMPLATES = {
    "ooda_audit": {
        "name": "OODA Sunday Audit Crew",
        "description": "Weekly business audit using OODA loop methodology",
        "agents": [
            {"role": "researcher", "task": "Gather weekly metrics from all systems"},
            {"role": "analyst", "task": "Analyze performance trends and anomalies"},
            {"role": "strategist", "task": "Create action recommendations"},
            {"role": "writer", "task": "Generate audit report"},
            {"role": "executor", "task": "Send report via WhatsApp"}
        ],
        "trigger": "scheduled_weekly"
    },
    "customer_rescue": {
        "name": "Customer Rescue Squad",
        "description": "Multi-agent team to save at-risk customers",
        "agents": [
            {"role": "analyst", "task": "Identify at-risk customers"},
            {"role": "researcher", "task": "Analyze customer history and preferences"},
            {"role": "strategist", "task": "Create personalized retention strategy"},
            {"role": "writer", "task": "Write personalized outreach messages"},
            {"role": "executor", "task": "Execute multi-channel outreach"}
        ],
        "trigger": "scheduled_daily"
    },
    "product_launch": {
        "name": "Product Launch Team",
        "description": "Coordinate new product launches",
        "agents": [
            {"role": "writer", "task": "Create product descriptions and marketing copy"},
            {"role": "researcher", "task": "Analyze competitor positioning"},
            {"role": "strategist", "task": "Plan launch sequence and channels"},
            {"role": "executor", "task": "Execute launch communications"},
            {"role": "auditor", "task": "Monitor launch metrics and feedback"}
        ],
        "trigger": "on_demand"
    },
    "content_factory": {
        "name": "Content Factory",
        "description": "Automated content generation pipeline",
        "agents": [
            {"role": "researcher", "task": "Research trending topics and keywords"},
            {"role": "writer", "task": "Generate product descriptions"},
            {"role": "writer", "task": "Create social media content"},
            {"role": "auditor", "task": "Review content quality"},
            {"role": "executor", "task": "Schedule and publish content"}
        ],
        "trigger": "scheduled_daily"
    },
    "competitor_intel": {
        "name": "Competitive Intelligence Unit",
        "description": "Monitor and analyze competitor activity",
        "agents": [
            {"role": "researcher", "task": "Scan competitor websites and pricing"},
            {"role": "analyst", "task": "Compare products and pricing"},
            {"role": "strategist", "task": "Identify opportunities and threats"},
            {"role": "writer", "task": "Generate intelligence report"}
        ],
        "trigger": "scheduled_weekly"
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentConfig(BaseModel):
    role: str
    task: str
    context: Optional[Dict[str, Any]] = None

class CrewConfig(BaseModel):
    name: str
    description: str
    agents: List[AgentConfig]
    trigger: str = "on_demand"
    input_data: Optional[Dict[str, Any]] = None

class CrewExecution(BaseModel):
    crew_id: Optional[str] = None  # Use template
    custom_crew: Optional[CrewConfig] = None
    input_data: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# CREW EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

async def execute_agent_task(role: str, task: str, context: Dict, previous_results: List[Dict]) -> Dict:
    """Execute a single agent's task"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"error": "LLM not configured"}
        
        agent_info = AGENT_ROLES.get(role, AGENT_ROLES["researcher"])
        
        # Build context from previous results
        prev_context = "\n".join([
            f"[{r['role']}]: {json.dumps(r['result'])[:500]}"
            for r in previous_results
        ])
        
        system_prompt = f"""You are a {agent_info['name']} in a multi-agent AI crew for ReRoots skincare.
Your skills: {', '.join(agent_info['skills'])}
Your tools: {', '.join(agent_info['tools'])}

You are working with other agents on a coordinated task. Use the context from previous agents.

Respond with actionable output in JSON format:
{{
  "analysis": "your analysis or findings",
  "actions": ["action1", "action2"],
  "recommendations": ["rec1", "rec2"],
  "data": {{...}},
  "next_steps": "what the next agent should focus on"
}}"""
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"crew_{secrets.token_hex(6)}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        user_prompt = f"""Task: {task}

Context: {json.dumps(context)}

Previous Agent Results:
{prev_context if prev_context else "You are the first agent."}

Execute your task and provide structured output."""
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            result = json.loads(response.strip())
        except:
            result = {"raw_output": response[:1000]}
        
        return {
            "role": role,
            "task": task,
            "result": result,
            "success": True
        }
        
    except Exception as e:
        return {
            "role": role,
            "task": task,
            "error": str(e),
            "success": False
        }


async def run_crew(execution_id: str, crew_config: Dict, input_data: Dict):
    """Run a complete crew execution"""
    results = []
    
    await db.crew_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {"status": "running"}}
    )
    
    try:
        for i, agent in enumerate(crew_config["agents"]):
            # Execute agent task
            result = await execute_agent_task(
                role=agent["role"],
                task=agent["task"],
                context={**input_data, "crew_name": crew_config["name"]},
                previous_results=results
            )
            
            results.append(result)
            
            # Update progress
            await db.crew_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "progress": (i + 1) / len(crew_config["agents"]) * 100,
                    "current_agent": agent["role"],
                    "results": results
                }}
            )
            
            # Check for failure
            if not result.get("success"):
                await db.crew_executions.update_one(
                    {"execution_id": execution_id},
                    {"$set": {
                        "status": "failed",
                        "error": result.get("error"),
                        "completed_at": datetime.now(timezone.utc)
                    }}
                )
                return
        
        # Generate final summary
        final_summary = await generate_crew_summary(crew_config["name"], results)
        
        # Complete
        await db.crew_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "status": "completed",
                "results": results,
                "summary": final_summary,
                "completed_at": datetime.now(timezone.utc)
            }}
        )
        
    except Exception as e:
        await db.crew_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc)
            }}
        )


async def generate_crew_summary(crew_name: str, results: List[Dict]) -> Dict:
    """Generate executive summary from crew results"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"summary": "Summary generation unavailable"}
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"summary_{secrets.token_hex(6)}",
            system_message="You are an executive summarizer. Create concise, actionable summaries."
        ).with_model("openai", "gpt-4o-mini")
        
        response = await chat.send_message(UserMessage(
            text=f"""Summarize the results from the "{crew_name}" crew execution:

{json.dumps(results, indent=2)[:3000]}

Provide a JSON summary:
{{
  "executive_summary": "2-3 sentence overview",
  "key_findings": ["finding1", "finding2"],
  "action_items": ["action1", "action2"],
  "metrics": {{}},
  "next_steps": "recommended next steps"
}}"""
        ))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {"executive_summary": response[:500]}
            
    except:
        return {"executive_summary": "Summary generation failed"}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/roles")
async def get_agent_roles():
    """Get available agent roles"""
    return {"roles": AGENT_ROLES}


@router.get("/templates")
async def get_crew_templates():
    """Get pre-built crew templates"""
    return {"templates": CREW_TEMPLATES}


@router.post("/execute")
async def execute_crew(data: CrewExecution, background_tasks: BackgroundTasks):
    """Execute a crew (template or custom)"""
    execution_id = f"crew_{secrets.token_hex(8)}"
    
    # Get crew config
    if data.crew_id and data.crew_id in CREW_TEMPLATES:
        crew_config = CREW_TEMPLATES[data.crew_id]
    elif data.custom_crew:
        crew_config = data.custom_crew.dict()
    else:
        raise HTTPException(status_code=400, detail="Must provide crew_id or custom_crew")
    
    # Create execution record
    await db.crew_executions.insert_one({
        "execution_id": execution_id,
        "crew_id": data.crew_id,
        "crew_name": crew_config["name"],
        "agents": crew_config["agents"],
        "input_data": data.input_data or {},
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(timezone.utc)
    })
    
    # Run in background
    background_tasks.add_task(
        run_crew,
        execution_id,
        crew_config,
        data.input_data or {}
    )
    
    return {
        "execution_id": execution_id,
        "crew_name": crew_config["name"],
        "agents_count": len(crew_config["agents"]),
        "status": "queued"
    }


@router.get("/execution/{execution_id}")
async def get_crew_execution(execution_id: str):
    """Get crew execution status and results"""
    execution = await db.crew_executions.find_one(
        {"execution_id": execution_id},
        {"_id": 0}
    )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {"execution": execution}


@router.get("/executions")
async def list_crew_executions(status: Optional[str] = None, limit: int = 20):
    """List recent crew executions"""
    query = {}
    if status:
        query["status"] = status
    
    executions = await db.crew_executions.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"executions": executions}


@router.post("/create")
async def create_custom_crew(crew: CrewConfig):
    """Create a new custom crew template"""
    crew_id = f"custom_{secrets.token_hex(6)}"
    
    await db.custom_crews.insert_one({
        "crew_id": crew_id,
        **crew.dict(),
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "crew_id": crew_id,
        "name": crew.name,
        "message": "Custom crew created"
    }
