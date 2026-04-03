"""
ReRoots AI Orchestrator - The Master Brain
Central intelligence that coordinates all AI agents, routes tasks, and executes workflows
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import json
import asyncio
import secrets
from enum import Enum

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator-brain"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

# All available AI agents and their capabilities
AGENT_REGISTRY = {
    "skin_analysis": {
        "name": "Skin Analysis AI",
        "endpoint": "/api/skin-analysis/analyze",
        "capabilities": ["analyze_skin", "detect_conditions", "recommend_routine"],
        "input_types": ["image", "base64"],
        "output_types": ["analysis_report", "product_recommendations"],
        "avg_response_time": 5,
        "cost_per_call": 0.05
    },
    "sentiment": {
        "name": "Sentiment Analysis AI",
        "endpoint": "/api/sentiment/analyze",
        "capabilities": ["analyze_sentiment", "detect_emotions", "extract_topics"],
        "input_types": ["text"],
        "output_types": ["sentiment_score", "emotion_breakdown"],
        "avg_response_time": 2,
        "cost_per_call": 0.01
    },
    "product_ai": {
        "name": "Product Description AI",
        "endpoint": "/api/product-ai/generate/description",
        "capabilities": ["generate_description", "create_tagline", "write_benefits"],
        "input_types": ["product_data"],
        "output_types": ["description", "tagline", "marketing_copy"],
        "avg_response_time": 3,
        "cost_per_call": 0.02
    },
    "translation": {
        "name": "Translation AI",
        "endpoint": "/api/translate/text",
        "capabilities": ["translate_text", "localize_content"],
        "input_types": ["text"],
        "output_types": ["translated_text"],
        "avg_response_time": 2,
        "cost_per_call": 0.01
    },
    "churn_prediction": {
        "name": "Churn Prediction AI",
        "endpoint": "/api/churn/predict",
        "capabilities": ["predict_churn", "identify_at_risk", "suggest_retention"],
        "input_types": ["user_id", "user_data"],
        "output_types": ["churn_probability", "retention_actions"],
        "avg_response_time": 3,
        "cost_per_call": 0.02
    },
    "inventory_ai": {
        "name": "Inventory AI",
        "endpoint": "/api/inventory-ai/predict",
        "capabilities": ["predict_demand", "optimize_stock", "reorder_alerts"],
        "input_types": ["product_id", "timeframe"],
        "output_types": ["demand_forecast", "reorder_list"],
        "avg_response_time": 4,
        "cost_per_call": 0.03
    },
    "weather_skincare": {
        "name": "Weather Skincare AI",
        "endpoint": "/api/weather-skincare/analyze/city",
        "capabilities": ["weather_recommendations", "seasonal_advice"],
        "input_types": ["location", "city"],
        "output_types": ["product_recommendations", "skincare_tips"],
        "avg_response_time": 3,
        "cost_per_call": 0.02
    },
    "document_scanner": {
        "name": "Document Scanner AI",
        "endpoint": "/api/document-scanner/scan",
        "capabilities": ["ocr", "extract_data", "parse_invoice"],
        "input_types": ["image", "base64", "pdf"],
        "output_types": ["extracted_text", "structured_data"],
        "avg_response_time": 5,
        "cost_per_call": 0.04
    },
    "video_generation": {
        "name": "Video Generation AI",
        "endpoint": "/api/video-gen/generate",
        "capabilities": ["create_video", "product_demo"],
        "input_types": ["prompt", "product_id"],
        "output_types": ["video_url"],
        "avg_response_time": 120,
        "cost_per_call": 0.50
    },
    "email_ai": {
        "name": "AI Email Generator",
        "endpoint": "/api/ai-email/generate",
        "capabilities": ["write_email", "campaign_copy", "personalize"],
        "input_types": ["context", "recipient_data"],
        "output_types": ["email_content"],
        "avg_response_time": 3,
        "cost_per_call": 0.02
    },
    "whatsapp": {
        "name": "WhatsApp Alerts",
        "endpoint": "/api/whatsapp/send",
        "capabilities": ["send_message", "send_template", "broadcast"],
        "input_types": ["phone", "message"],
        "output_types": ["delivery_status"],
        "avg_response_time": 2,
        "cost_per_call": 0.01
    },
    "sms": {
        "name": "SMS Alerts",
        "endpoint": "/api/sms/send",
        "capabilities": ["send_sms", "send_otp", "bulk_sms"],
        "input_types": ["phone", "message"],
        "output_types": ["delivery_status"],
        "avg_response_time": 2,
        "cost_per_call": 0.02
    },
    "appointments": {
        "name": "Appointment Scheduler",
        "endpoint": "/api/appointments/book",
        "capabilities": ["book_appointment", "check_availability", "reschedule"],
        "input_types": ["customer_data", "datetime"],
        "output_types": ["appointment_confirmation"],
        "avg_response_time": 1,
        "cost_per_call": 0.01
    }
}

# Pre-built workflow templates
WORKFLOW_TEMPLATES = {
    "new_customer_onboarding": {
        "name": "New Customer Onboarding",
        "description": "Complete onboarding flow for new customers",
        "trigger": "new_customer_signup",
        "steps": [
            {"agent": "skin_analysis", "action": "analyze_skin", "wait_for_input": True},
            {"agent": "product_ai", "action": "recommend_products", "input_from": "step_1"},
            {"agent": "email_ai", "action": "write_welcome_email", "input_from": "step_2"},
            {"agent": "whatsapp", "action": "send_welcome", "input_from": "step_3"}
        ]
    },
    "order_processing": {
        "name": "Order Processing",
        "description": "Automated order confirmation and updates",
        "trigger": "new_order",
        "steps": [
            {"agent": "sms", "action": "send_confirmation"},
            {"agent": "inventory_ai", "action": "update_stock"},
            {"agent": "email_ai", "action": "send_receipt"},
            {"agent": "churn_prediction", "action": "update_customer_score"}
        ]
    },
    "customer_retention": {
        "name": "Customer Retention Campaign",
        "description": "Identify and re-engage at-risk customers",
        "trigger": "scheduled_daily",
        "steps": [
            {"agent": "churn_prediction", "action": "identify_at_risk"},
            {"agent": "product_ai", "action": "create_personalized_offer", "input_from": "step_1"},
            {"agent": "email_ai", "action": "write_retention_email", "input_from": "step_2"},
            {"agent": "whatsapp", "action": "send_offer", "input_from": "step_2"}
        ]
    },
    "product_launch": {
        "name": "Product Launch Campaign",
        "description": "Automated multi-channel product launch",
        "trigger": "new_product",
        "steps": [
            {"agent": "product_ai", "action": "generate_description"},
            {"agent": "video_generation", "action": "create_demo", "input_from": "step_1"},
            {"agent": "translation", "action": "translate_all", "input_from": "step_1"},
            {"agent": "email_ai", "action": "write_announcement", "input_from": "step_1"},
            {"agent": "whatsapp", "action": "broadcast_launch"}
        ]
    },
    "review_analysis": {
        "name": "Review Analysis & Response",
        "description": "Analyze reviews and generate responses",
        "trigger": "new_review",
        "steps": [
            {"agent": "sentiment", "action": "analyze_review"},
            {"agent": "email_ai", "action": "generate_response", "input_from": "step_1", "condition": "sentiment < 0.3"},
            {"agent": "product_ai", "action": "suggest_improvements", "input_from": "step_1"}
        ]
    },
    "inventory_management": {
        "name": "Daily Inventory Check",
        "description": "Automated inventory monitoring and alerts",
        "trigger": "scheduled_daily",
        "steps": [
            {"agent": "inventory_ai", "action": "predict_demand"},
            {"agent": "inventory_ai", "action": "get_reorder_list"},
            {"agent": "email_ai", "action": "write_inventory_report", "input_from": "step_1,step_2"},
            {"agent": "sms", "action": "alert_low_stock", "condition": "critical_items > 0"}
        ]
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class OrchestratorCommand(BaseModel):
    command: str  # Natural language command
    context: Optional[Dict[str, Any]] = None
    priority: TaskPriority = TaskPriority.NORMAL
    async_execution: bool = True

class WorkflowExecution(BaseModel):
    workflow_id: str
    input_data: Optional[Dict[str, Any]] = None
    priority: TaskPriority = TaskPriority.NORMAL

class CustomWorkflow(BaseModel):
    name: str
    description: str
    trigger: str
    steps: List[Dict[str, Any]]

class AgentTask(BaseModel):
    agent_id: str
    action: str
    input_data: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR BRAIN - NATURAL LANGUAGE UNDERSTANDING
# ═══════════════════════════════════════════════════════════════════════════════

ORCHESTRATOR_SYSTEM_PROMPT = """You are the ReRoots AI Orchestrator - the Master Brain that coordinates all AI agents.

Your job is to:
1. Understand natural language commands from the user
2. Break them down into actionable tasks for specific AI agents
3. Determine the optimal sequence of agent calls
4. Handle dependencies between tasks

Available AI Agents and their capabilities:
{agent_info}

Available Workflow Templates:
{workflow_info}

When given a command, respond with a JSON execution plan:
{{
  "understood_intent": "brief description of what user wants",
  "execution_plan": [
    {{
      "step": 1,
      "agent": "agent_id",
      "action": "specific_action",
      "input": {{}},
      "depends_on": null or step number,
      "condition": null or "condition to check"
    }}
  ],
  "estimated_time": "X seconds/minutes",
  "estimated_cost": X.XX,
  "requires_user_input": true/false,
  "input_needed": "description of what input is needed" or null
}}

If the command matches a workflow template, suggest using it.
If the command is unclear, ask for clarification.
Always optimize for efficiency - batch similar operations, use TOON compression."""


async def understand_command(command: str, context: Dict = None) -> Dict:
    """Use AI to understand natural language command and create execution plan"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"error": "Orchestrator AI not configured"}
        
        # Build agent info
        agent_info = "\n".join([
            f"- {aid}: {a['name']} - capabilities: {', '.join(a['capabilities'])}"
            for aid, a in AGENT_REGISTRY.items()
        ])
        
        # Build workflow info
        workflow_info = "\n".join([
            f"- {wid}: {w['name']} - {w['description']}"
            for wid, w in WORKFLOW_TEMPLATES.items()
        ])
        
        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(
            agent_info=agent_info,
            workflow_info=workflow_info
        )
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"orchestrator_{secrets.token_hex(6)}",
            system_message=system_prompt
        ).with_model("openai", "gpt-5.2")
        
        context_str = f"\nContext: {json.dumps(context)}" if context else ""
        
        response = await chat.send_message(UserMessage(
            text=f"Command: {command}{context_str}"
        ))
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            return json.loads(response.strip())
        except:
            return {
                "understood_intent": command,
                "execution_plan": [],
                "error": "Failed to parse execution plan",
                "raw_response": response[:500]
            }
            
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# TASK EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

# Active WebSocket connections for real-time updates
active_connections: Set[WebSocket] = set()

async def broadcast_update(message: Dict):
    """Broadcast update to all connected clients"""
    for ws in active_connections.copy():
        try:
            await ws.send_json(message)
        except:
            active_connections.discard(ws)


async def execute_agent_task(agent_id: str, action: str, input_data: Dict, task_id: str) -> Dict:
    """Execute a single agent task"""
    import httpx
    
    if agent_id not in AGENT_REGISTRY:
        return {"error": f"Unknown agent: {agent_id}"}
    
    agent = AGENT_REGISTRY[agent_id]
    
    # Broadcast task start
    await broadcast_update({
        "type": "task_update",
        "task_id": task_id,
        "agent": agent_id,
        "status": "running",
        "action": action
    })
    
    try:
        # Get backend URL
        backend_url = os.environ.get("BACKEND_URL", "http://localhost:8001")
        
        async with httpx.AsyncClient(timeout=300) as client:
            # Make request to agent endpoint
            endpoint = agent["endpoint"]
            
            # Prepare request based on agent type
            if agent_id == "skin_analysis":
                response = await client.post(
                    f"{backend_url}{endpoint}",
                    json=input_data
                )
            elif agent_id == "sentiment":
                response = await client.post(
                    f"{backend_url}{endpoint}",
                    json={"text": input_data.get("text", ""), "context": input_data.get("context")}
                )
            elif agent_id == "translation":
                response = await client.post(
                    f"{backend_url}{endpoint}",
                    json=input_data
                )
            elif agent_id == "churn_prediction":
                user_id = input_data.get("user_id", "")
                response = await client.post(
                    f"{backend_url}/api/churn/predict/{user_id}"
                )
            elif agent_id in ["whatsapp", "sms"]:
                response = await client.post(
                    f"{backend_url}{endpoint}",
                    json=input_data
                )
            else:
                response = await client.post(
                    f"{backend_url}{endpoint}",
                    json=input_data
                )
            
            result = response.json() if response.status_code == 200 else {"error": response.text}
            
            # Broadcast completion
            await broadcast_update({
                "type": "task_update",
                "task_id": task_id,
                "agent": agent_id,
                "status": "completed" if response.status_code == 200 else "failed",
                "result": result
            })
            
            return result
            
    except Exception as e:
        error_result = {"error": str(e)}
        await broadcast_update({
            "type": "task_update",
            "task_id": task_id,
            "agent": agent_id,
            "status": "failed",
            "error": str(e)
        })
        return error_result


async def execute_workflow(workflow_id: str, input_data: Dict, execution_id: str) -> Dict:
    """Execute a complete workflow"""
    if workflow_id not in WORKFLOW_TEMPLATES:
        return {"error": f"Unknown workflow: {workflow_id}"}
    
    workflow = WORKFLOW_TEMPLATES[workflow_id]
    results = {}
    
    # Broadcast workflow start
    await broadcast_update({
        "type": "workflow_update",
        "execution_id": execution_id,
        "workflow": workflow_id,
        "status": "started",
        "total_steps": len(workflow["steps"])
    })
    
    for i, step in enumerate(workflow["steps"], 1):
        step_id = f"{execution_id}_step_{i}"
        
        # Check condition if present
        if "condition" in step and step["condition"]:
            # Evaluate condition (simplified)
            condition_met = evaluate_condition(step["condition"], results)
            if not condition_met:
                results[f"step_{i}"] = {"skipped": True, "reason": "Condition not met"}
                continue
        
        # Get input for this step
        step_input = input_data.copy()
        if "input_from" in step:
            # Get output from previous step(s)
            prev_steps = step["input_from"].split(",")
            for ps in prev_steps:
                if ps in results:
                    step_input.update({"previous_result": results[ps]})
        
        # Execute step
        result = await execute_agent_task(
            step["agent"],
            step.get("action", "default"),
            step_input,
            step_id
        )
        
        results[f"step_{i}"] = result
        
        # Check for failure
        if "error" in result and not result.get("continue_on_error"):
            await broadcast_update({
                "type": "workflow_update",
                "execution_id": execution_id,
                "workflow": workflow_id,
                "status": "failed",
                "failed_at_step": i,
                "error": result["error"]
            })
            
            # Store execution record
            await db.workflow_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": "failed",
                    "failed_at_step": i,
                    "results": results,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
            return {"status": "failed", "failed_at_step": i, "results": results}
    
    # Workflow completed successfully
    await broadcast_update({
        "type": "workflow_update",
        "execution_id": execution_id,
        "workflow": workflow_id,
        "status": "completed"
    })
    
    # Store execution record
    await db.workflow_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {
            "status": "completed",
            "results": results,
            "completed_at": datetime.now(timezone.utc)
        }}
    )
    
    return {"status": "completed", "results": results}


def evaluate_condition(condition: str, results: Dict) -> bool:
    """Evaluate a simple condition"""
    try:
        # Simple condition evaluation
        if "sentiment < " in condition:
            threshold = float(condition.split("<")[1].strip())
            for step_result in results.values():
                if isinstance(step_result, dict) and "score" in step_result:
                    return step_result["score"] < threshold
        
        if "critical_items > " in condition:
            threshold = int(condition.split(">")[1].strip())
            for step_result in results.values():
                if isinstance(step_result, dict) and "critical_count" in step_result:
                    return step_result["critical_count"] > threshold
        
        return True  # Default to true if can't evaluate
    except:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/agents")
async def get_available_agents():
    """Get all available AI agents and their capabilities"""
    return {"agents": AGENT_REGISTRY}


@router.get("/workflows")
async def get_workflow_templates():
    """Get all available workflow templates"""
    return {"workflows": WORKFLOW_TEMPLATES}


@router.post("/command")
async def execute_command(data: OrchestratorCommand, background_tasks: BackgroundTasks):
    """Execute a natural language command"""
    # Create execution record
    execution_id = f"exec_{secrets.token_hex(8)}"
    
    execution_record = {
        "execution_id": execution_id,
        "command": data.command,
        "context": data.context,
        "priority": data.priority,
        "status": "analyzing",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.orchestrator_executions.insert_one(execution_record)
    
    # Understand the command
    plan = await understand_command(data.command, data.context)
    
    if "error" in plan:
        await db.orchestrator_executions.update_one(
            {"execution_id": execution_id},
            {"$set": {"status": "failed", "error": plan["error"]}}
        )
        return {"execution_id": execution_id, "status": "failed", "error": plan["error"]}
    
    # Update with execution plan
    await db.orchestrator_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {"execution_plan": plan, "status": "planned"}}
    )
    
    # If async execution, run in background
    if data.async_execution and plan.get("execution_plan"):
        background_tasks.add_task(
            run_execution_plan,
            execution_id,
            plan,
            data.context or {}
        )
        return {
            "execution_id": execution_id,
            "status": "executing",
            "plan": plan,
            "message": "Execution started. Connect to WebSocket for real-time updates."
        }
    
    # Synchronous execution
    if plan.get("execution_plan"):
        results = await run_execution_plan_sync(execution_id, plan, data.context or {})
        return {
            "execution_id": execution_id,
            "status": "completed",
            "plan": plan,
            "results": results
        }
    
    return {
        "execution_id": execution_id,
        "status": "planned",
        "plan": plan,
        "requires_confirmation": plan.get("requires_user_input", False)
    }


async def run_execution_plan(execution_id: str, plan: Dict, context: Dict):
    """Run execution plan in background"""
    await db.orchestrator_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {"status": "executing"}}
    )
    
    results = {}
    
    for step in plan.get("execution_plan", []):
        step_num = step.get("step", 0)
        agent_id = step.get("agent")
        action = step.get("action")
        step_input = {**context, **step.get("input", {})}
        
        # Check dependencies
        if step.get("depends_on"):
            dep_step = f"step_{step['depends_on']}"
            if dep_step in results:
                step_input["previous_result"] = results[dep_step]
        
        # Execute step
        result = await execute_agent_task(
            agent_id,
            action,
            step_input,
            f"{execution_id}_step_{step_num}"
        )
        
        results[f"step_{step_num}"] = result
        
        # Check for failure
        if "error" in result:
            await db.orchestrator_executions.update_one(
                {"execution_id": execution_id},
                {"$set": {
                    "status": "failed",
                    "results": results,
                    "failed_at_step": step_num,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            return
    
    # Complete
    await db.orchestrator_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {
            "status": "completed",
            "results": results,
            "completed_at": datetime.now(timezone.utc)
        }}
    )


async def run_execution_plan_sync(execution_id: str, plan: Dict, context: Dict) -> Dict:
    """Run execution plan synchronously"""
    results = {}
    
    for step in plan.get("execution_plan", []):
        step_num = step.get("step", 0)
        agent_id = step.get("agent")
        action = step.get("action")
        step_input = {**context, **step.get("input", {})}
        
        if step.get("depends_on"):
            dep_step = f"step_{step['depends_on']}"
            if dep_step in results:
                step_input["previous_result"] = results[dep_step]
        
        result = await execute_agent_task(
            agent_id,
            action,
            step_input,
            f"{execution_id}_step_{step_num}"
        )
        
        results[f"step_{step_num}"] = result
    
    return results


@router.post("/workflow/execute")
async def execute_workflow_endpoint(data: WorkflowExecution, background_tasks: BackgroundTasks):
    """Execute a predefined workflow"""
    execution_id = f"wf_{secrets.token_hex(8)}"
    
    # Create execution record
    await db.workflow_executions.insert_one({
        "execution_id": execution_id,
        "workflow_id": data.workflow_id,
        "input_data": data.input_data,
        "priority": data.priority,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    })
    
    # Execute in background
    background_tasks.add_task(
        execute_workflow,
        data.workflow_id,
        data.input_data or {},
        execution_id
    )
    
    return {
        "execution_id": execution_id,
        "workflow_id": data.workflow_id,
        "status": "started",
        "message": "Workflow execution started"
    }


@router.post("/workflow/create")
async def create_custom_workflow(data: CustomWorkflow):
    """Create a custom workflow"""
    workflow_id = f"custom_{secrets.token_hex(6)}"
    
    workflow = {
        "workflow_id": workflow_id,
        "name": data.name,
        "description": data.description,
        "trigger": data.trigger,
        "steps": data.steps,
        "created_at": datetime.now(timezone.utc),
        "is_custom": True
    }
    
    await db.custom_workflows.insert_one(workflow)
    
    return {
        "workflow_id": workflow_id,
        "message": "Custom workflow created successfully"
    }


@router.get("/execution/{execution_id}")
async def get_execution_status(execution_id: str):
    """Get status of an execution"""
    # Check orchestrator executions
    execution = await db.orchestrator_executions.find_one(
        {"execution_id": execution_id},
        {"_id": 0}
    )
    
    if not execution:
        # Check workflow executions
        execution = await db.workflow_executions.find_one(
            {"execution_id": execution_id},
            {"_id": 0}
        )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {"execution": execution}


@router.get("/executions")
async def get_recent_executions(limit: int = 20):
    """Get recent executions"""
    orchestrator_execs = await db.orchestrator_executions.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    workflow_execs = await db.workflow_executions.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {
        "orchestrator_executions": orchestrator_execs,
        "workflow_executions": workflow_execs
    }


@router.post("/task")
async def execute_single_task(data: AgentTask, background_tasks: BackgroundTasks):
    """Execute a single agent task directly"""
    task_id = f"task_{secrets.token_hex(8)}"
    
    # Store task
    await db.agent_tasks.insert_one({
        "task_id": task_id,
        "agent_id": data.agent_id,
        "action": data.action,
        "input_data": data.input_data,
        "priority": data.priority,
        "status": "queued",
        "created_at": datetime.now(timezone.utc)
    })
    
    # Execute
    background_tasks.add_task(
        execute_and_store_task,
        task_id,
        data.agent_id,
        data.action,
        data.input_data
    )
    
    return {"task_id": task_id, "status": "queued"}


async def execute_and_store_task(task_id: str, agent_id: str, action: str, input_data: Dict):
    """Execute task and store result"""
    result = await execute_agent_task(agent_id, action, input_data, task_id)
    
    await db.agent_tasks.update_one(
        {"task_id": task_id},
        {"$set": {
            "status": "completed" if "error" not in result else "failed",
            "result": result,
            "completed_at": datetime.now(timezone.utc)
        }}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH & MONITORING
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def get_orchestrator_health():
    """Get health status of orchestrator and all agents"""
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    
    # Count recent executions
    recent_commands = await db.orchestrator_executions.count_documents({
        "created_at": {"$gte": hour_ago}
    })
    
    recent_workflows = await db.workflow_executions.count_documents({
        "created_at": {"$gte": hour_ago}
    })
    
    # Count failures
    failed_commands = await db.orchestrator_executions.count_documents({
        "created_at": {"$gte": hour_ago},
        "status": "failed"
    })
    
    # Agent health (simplified)
    agent_health = {}
    for agent_id in AGENT_REGISTRY.keys():
        agent_tasks = await db.agent_tasks.count_documents({
            "agent_id": agent_id,
            "created_at": {"$gte": hour_ago}
        })
        agent_failures = await db.agent_tasks.count_documents({
            "agent_id": agent_id,
            "created_at": {"$gte": hour_ago},
            "status": "failed"
        })
        
        success_rate = 100 if agent_tasks == 0 else ((agent_tasks - agent_failures) / agent_tasks) * 100
        
        agent_health[agent_id] = {
            "tasks_last_hour": agent_tasks,
            "failures": agent_failures,
            "success_rate": round(success_rate, 2),
            "status": "healthy" if success_rate >= 90 else "degraded" if success_rate >= 50 else "unhealthy"
        }
    
    overall_health = sum(1 for a in agent_health.values() if a["status"] == "healthy") / len(agent_health) * 100
    
    return {
        "orchestrator_status": "healthy" if overall_health >= 80 else "degraded",
        "overall_health_score": round(overall_health, 2),
        "executions_last_hour": {
            "commands": recent_commands,
            "workflows": recent_workflows,
            "failures": failed_commands
        },
        "agent_health": agent_health,
        "active_websocket_connections": len(active_connections)
    }


@router.get("/queue")
async def get_task_queue():
    """Get current task queue"""
    pending_tasks = await db.agent_tasks.find(
        {"status": "queued"},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    
    running_tasks = await db.agent_tasks.find(
        {"status": "running"},
        {"_id": 0}
    ).to_list(50)
    
    return {
        "pending": pending_tasks,
        "running": running_tasks,
        "pending_count": len(pending_tasks),
        "running_count": len(running_tasks)
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET FOR REAL-TIME UPDATES
# ═══════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws")
async def orchestrator_websocket(websocket: WebSocket):
    """WebSocket for real-time orchestrator updates"""
    await websocket.accept()
    active_connections.add(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Orchestrator"
        })
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle ping
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                # Handle command execution request
                elif message.get("type") == "command":
                    plan = await understand_command(message.get("command", ""))
                    await websocket.send_json({
                        "type": "plan",
                        "plan": plan
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        active_connections.discard(websocket)
    except Exception:
        active_connections.discard(websocket)
