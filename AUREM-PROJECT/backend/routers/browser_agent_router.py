"""
ReRoots AI Browser Agent - PinchTab-style Browser Automation
AI-controlled browser for admin panel actions, competitor monitoring, and data extraction
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import asyncio
import json
import secrets

router = APIRouter(prefix="/api/browser-agent", tags=["browser-agent"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER AGENT CAPABILITIES
# ═══════════════════════════════════════════════════════════════════════════════

BROWSER_CAPABILITIES = {
    "navigate": "Navigate to URL",
    "click": "Click element by selector",
    "type": "Type text into input",
    "extract": "Extract text/data from page",
    "screenshot": "Capture page screenshot",
    "wait": "Wait for element or time",
    "scroll": "Scroll page",
    "evaluate": "Execute JavaScript",
    "fill_form": "Fill form with data",
    "download": "Download file from page"
}

# Pre-defined browser tasks
BROWSER_TASKS = {
    "check_order_status": {
        "name": "Check Order Status",
        "description": "Navigate to admin and check order status",
        "steps": [
            {"action": "navigate", "url": "/admin/orders"},
            {"action": "wait", "selector": ".order-table"},
            {"action": "extract", "selector": ".order-row", "multiple": True}
        ]
    },
    "competitor_price_check": {
        "name": "Competitor Price Monitor",
        "description": "Check competitor pricing on target products",
        "steps": [
            {"action": "navigate", "url": "{competitor_url}"},
            {"action": "wait", "selector": ".product-price"},
            {"action": "extract", "selector": ".product-card", "multiple": True}
        ]
    },
    "inventory_audit": {
        "name": "Inventory Audit",
        "description": "Audit current inventory from admin panel",
        "steps": [
            {"action": "navigate", "url": "/admin/inventory"},
            {"action": "wait", "selector": ".inventory-table"},
            {"action": "extract", "selector": ".inventory-row", "multiple": True}
        ]
    },
    "customer_lookup": {
        "name": "Customer Lookup",
        "description": "Look up customer details by email or ID",
        "steps": [
            {"action": "navigate", "url": "/admin/customers"},
            {"action": "type", "selector": "#search", "text": "{customer_query}"},
            {"action": "click", "selector": "#search-btn"},
            {"action": "wait", "selector": ".customer-result"},
            {"action": "extract", "selector": ".customer-details"}
        ]
    },
    "analytics_report": {
        "name": "Analytics Report Extraction",
        "description": "Extract analytics data from dashboard",
        "steps": [
            {"action": "navigate", "url": "/admin/analytics"},
            {"action": "wait", "selector": ".analytics-container"},
            {"action": "screenshot", "name": "analytics"},
            {"action": "extract", "selector": ".metric-card", "multiple": True}
        ]
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class BrowserAction(BaseModel):
    action: str  # navigate, click, type, extract, screenshot, wait, scroll, evaluate
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    timeout: int = 30
    multiple: bool = False

class BrowserTask(BaseModel):
    task_id: Optional[str] = None  # Use predefined task
    steps: Optional[List[BrowserAction]] = None  # Custom steps
    variables: Optional[Dict[str, str]] = None  # Variables to substitute
    save_results: bool = True

class AIBrowserCommand(BaseModel):
    command: str  # Natural language command
    context: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class BrowserSession:
    """Manages browser sessions using Playwright"""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.session_id = None
    
    async def start(self, headless: bool = True):
        """Start browser session"""
        try:
            from playwright.async_api import async_playwright
            
            self.session_id = f"browser_{secrets.token_hex(8)}"
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self.page = await self.context.new_page()
            return self.session_id
        except Exception as e:
            return {"error": f"Failed to start browser: {str(e)}"}
    
    async def execute_action(self, action: BrowserAction) -> Dict:
        """Execute a single browser action"""
        if not self.page:
            return {"error": "No active browser session"}
        
        try:
            if action.action == "navigate":
                await self.page.goto(action.url, timeout=action.timeout * 1000)
                return {"success": True, "url": self.page.url}
            
            elif action.action == "click":
                await self.page.click(action.selector, timeout=action.timeout * 1000)
                return {"success": True, "clicked": action.selector}
            
            elif action.action == "type":
                await self.page.fill(action.selector, action.text, timeout=action.timeout * 1000)
                return {"success": True, "typed": len(action.text)}
            
            elif action.action == "extract":
                if action.multiple:
                    elements = await self.page.query_selector_all(action.selector)
                    data = [await el.inner_text() for el in elements]
                else:
                    element = await self.page.query_selector(action.selector)
                    data = await element.inner_text() if element else None
                return {"success": True, "data": data}
            
            elif action.action == "screenshot":
                path = f"/tmp/browser_{action.text or 'page'}_{secrets.token_hex(4)}.png"
                await self.page.screenshot(path=path)
                return {"success": True, "path": path}
            
            elif action.action == "wait":
                if action.selector:
                    await self.page.wait_for_selector(action.selector, timeout=action.timeout * 1000)
                else:
                    await asyncio.sleep(action.timeout)
                return {"success": True, "waited": action.selector or f"{action.timeout}s"}
            
            elif action.action == "scroll":
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                return {"success": True, "scrolled": True}
            
            elif action.action == "evaluate":
                result = await self.page.evaluate(action.text)
                return {"success": True, "result": result}
            
            else:
                return {"error": f"Unknown action: {action.action}"}
                
        except Exception as e:
            return {"error": str(e), "action": action.action}
    
    async def close(self):
        """Close browser session"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None


# Global session pool
browser_sessions: Dict[str, BrowserSession] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/capabilities")
async def get_browser_capabilities():
    """Get browser agent capabilities"""
    return {
        "actions": BROWSER_CAPABILITIES,
        "predefined_tasks": {k: {"name": v["name"], "description": v["description"]} for k, v in BROWSER_TASKS.items()}
    }


@router.post("/session/start")
async def start_browser_session(headless: bool = True):
    """Start a new browser session"""
    session = BrowserSession()
    result = await session.start(headless)
    
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    browser_sessions[result] = session
    
    # Log session
    await db.browser_sessions.insert_one({
        "session_id": result,
        "started_at": datetime.now(timezone.utc),
        "status": "active"
    })
    
    return {"session_id": result, "status": "active"}


@router.post("/session/{session_id}/action")
async def execute_browser_action(session_id: str, action: BrowserAction):
    """Execute a single action in browser session"""
    if session_id not in browser_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = browser_sessions[session_id]
    result = await session.execute_action(action)
    
    # Log action
    await db.browser_actions.insert_one({
        "session_id": session_id,
        "action": action.action,
        "selector": action.selector,
        "result": result,
        "timestamp": datetime.now(timezone.utc)
    })
    
    return result


@router.post("/task/execute")
async def execute_browser_task(task: BrowserTask, background_tasks: BackgroundTasks):
    """Execute a complete browser task (predefined or custom)"""
    execution_id = f"task_{secrets.token_hex(8)}"
    
    # Get steps
    if task.task_id and task.task_id in BROWSER_TASKS:
        steps = BROWSER_TASKS[task.task_id]["steps"]
    elif task.steps:
        steps = [s.dict() for s in task.steps]
    else:
        raise HTTPException(status_code=400, detail="Must provide task_id or steps")
    
    # Substitute variables
    if task.variables:
        steps_str = json.dumps(steps)
        for key, value in task.variables.items():
            steps_str = steps_str.replace(f"{{{key}}}", value)
        steps = json.loads(steps_str)
    
    # Create execution record
    await db.browser_task_executions.insert_one({
        "execution_id": execution_id,
        "task_id": task.task_id,
        "steps": steps,
        "status": "running",
        "started_at": datetime.now(timezone.utc)
    })
    
    # Execute in background
    background_tasks.add_task(run_browser_task, execution_id, steps, task.save_results)
    
    return {
        "execution_id": execution_id,
        "status": "running",
        "task_id": task.task_id
    }


async def run_browser_task(execution_id: str, steps: List[Dict], save_results: bool):
    """Background task execution"""
    session = BrowserSession()
    await session.start(headless=True)
    
    results = []
    
    try:
        for i, step in enumerate(steps):
            action = BrowserAction(**step)
            result = await session.execute_action(action)
            results.append({
                "step": i + 1,
                "action": step.get("action"),
                "result": result
            })
            
            if "error" in result:
                break
        
        status = "completed" if all("error" not in r["result"] for r in results) else "failed"
        
    except Exception as e:
        status = "failed"
        results.append({"error": str(e)})
    
    finally:
        await session.close()
    
    # Update execution record
    await db.browser_task_executions.update_one(
        {"execution_id": execution_id},
        {"$set": {
            "status": status,
            "results": results if save_results else None,
            "completed_at": datetime.now(timezone.utc)
        }}
    )


@router.post("/ai-command")
async def execute_ai_browser_command(data: AIBrowserCommand):
    """Execute natural language browser command using AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="AI not configured")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"browser_ai_{secrets.token_hex(6)}",
            system_message=f"""You are a browser automation AI. Convert natural language commands into browser action sequences.

Available actions:
{json.dumps(BROWSER_CAPABILITIES, indent=2)}

Available predefined tasks:
{json.dumps({k: v["description"] for k, v in BROWSER_TASKS.items()}, indent=2)}

Respond with JSON:
{{
  "use_predefined_task": "task_id or null",
  "variables": {{}},
  "custom_steps": [] // Only if not using predefined task
}}"""
        ).with_model("openai", "gpt-5.2")
        
        context_str = f"\nContext: {data.context}" if data.context else ""
        
        response = await chat.send_message(UserMessage(
            text=f"Command: {data.command}{context_str}"
        ))
        
        # Parse response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            plan = json.loads(response.strip())
        except:
            return {"error": "Failed to parse AI response", "raw": response[:500]}
        
        return {
            "command": data.command,
            "execution_plan": plan,
            "message": "Use /task/execute with this plan to run"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def close_browser_session(session_id: str):
    """Close a browser session"""
    if session_id in browser_sessions:
        await browser_sessions[session_id].close()
        del browser_sessions[session_id]
        
        await db.browser_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "closed", "closed_at": datetime.now(timezone.utc)}}
        )
        
        return {"success": True, "session_id": session_id}
    
    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/task/{execution_id}")
async def get_task_status(execution_id: str):
    """Get browser task execution status"""
    execution = await db.browser_task_executions.find_one(
        {"execution_id": execution_id},
        {"_id": 0}
    )
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return {"execution": execution}
