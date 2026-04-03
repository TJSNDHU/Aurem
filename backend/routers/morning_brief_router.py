"""
AUREM Morning Brief Router
Daily intelligence briefing for the Envoy Agent + Architecture Documentation

Endpoints:
- GET /api/aurem/morning-brief - Aggregated weather, time, and pending tasks
- GET /api/aurem/morning-brief/narration - TTS-ready narration only
- GET /api/aurem/architecture - Full platform architecture overview
- GET /api/aurem/architecture/roi - ROI Calculator with live metrics
- GET /api/aurem/architecture/a2a - Agent-to-Agent protocol specs
- POST /api/aurem/tasks - Create new task
- DELETE /api/aurem/tasks/{task_id} - Complete task
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import os

from fastapi import APIRouter, HTTPException, Query
import pytz
import httpx

router = APIRouter(prefix="/api/aurem", tags=["AUREM Morning Brief & Architecture"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# Business timezone (Mississauga/Eastern)
BUSINESS_TIMEZONE = "America/Toronto"
DEFAULT_LOCATION = "Mississauga,CA"


# ==================== WEATHER SERVICE ====================

async def fetch_weather(location: str = DEFAULT_LOCATION) -> Dict[str, Any]:
    """
    Fetch current weather data.
    Uses OpenWeatherMap API if configured, otherwise returns mock data.
    """
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    
    if api_key:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openweathermap.org/data/2.5/weather",
                    params={
                        "q": location,
                        "appid": api_key,
                        "units": "metric"
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "temperature": round(data["main"]["temp"]),
                        "feels_like": round(data["main"]["feels_like"]),
                        "condition": data["weather"][0]["main"],
                        "description": data["weather"][0]["description"],
                        "humidity": data["main"]["humidity"],
                        "wind_speed": round(data["wind"]["speed"] * 3.6),
                        "location": data["name"],
                        "icon": data["weather"][0]["icon"],
                        "source": "openweathermap"
                    }
        except Exception as e:
            logger.warning(f"[MorningBrief] Weather API failed: {e}")
    
    # Mock weather data for demo
    tz = pytz.timezone(BUSINESS_TIMEZONE)
    now = datetime.now(tz)
    hour = now.hour
    
    month = now.month
    if month in [12, 1, 2]:
        temp = -5 + (hour - 6) * 0.5
        condition = "Snow" if hour < 10 else "Cloudy"
    elif month in [3, 4, 5]:
        temp = 8 + (hour - 6) * 0.8
        condition = "Partly Cloudy"
    elif month in [6, 7, 8]:
        temp = 20 + (hour - 6) * 1.2
        condition = "Sunny" if hour > 8 else "Clear"
    else:
        temp = 12 + (hour - 6) * 0.6
        condition = "Cloudy"
    
    return {
        "temperature": round(temp),
        "feels_like": round(temp - 2),
        "condition": condition,
        "description": condition.lower(),
        "humidity": 65,
        "wind_speed": 15,
        "location": "Mississauga",
        "icon": "03d",
        "source": "mock"
    }


# ==================== REDIS TASKS SERVICE ====================

async def fetch_pending_tasks(business_id: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Fetch pending tasks from Redis.
    Falls back to MongoDB if Redis not available.
    """
    tasks = []
    
    try:
        import redis.asyncio as redis
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)
        
        task_key = f"aurem:tasks:{business_id}"
        raw_tasks = await r.zrange(task_key, 0, limit - 1, withscores=True)
        
        if raw_tasks:
            import json
            for task_data, score in raw_tasks:
                try:
                    task = json.loads(task_data)
                    task["priority_score"] = score
                    tasks.append(task)
                except (json.JSONDecodeError, TypeError):
                    pass
        
        await r.close()
        
        if tasks:
            return tasks
            
    except Exception as e:
        logger.warning(f"[MorningBrief] Redis fetch failed: {e}")
    
    try:
        db = get_db()
        tasks_collection = db["aurem_tasks"]
        
        cursor = tasks_collection.find(
            {
                "business_id": business_id,
                "status": {"$in": ["pending", "in_progress"]}
            },
            {"_id": 0}
        ).sort("priority", 1).limit(limit)
        
        tasks = await cursor.to_list(limit)
        
        if tasks:
            return tasks
            
    except Exception as e:
        logger.warning(f"[MorningBrief] MongoDB tasks fetch failed: {e}")
    
    # Return demo tasks if none found
    return [
        {
            "id": "task_001",
            "title": "Follow up with VIP client (Tejinder)",
            "description": "Schedule consultation for PDRN treatment",
            "priority": 1,
            "priority_label": "high",
            "due_date": datetime.now(pytz.timezone(BUSINESS_TIMEZONE)).strftime("%Y-%m-%d"),
            "category": "client_followup",
            "source": "demo"
        },
        {
            "id": "task_002", 
            "title": "Review skincare inventory levels",
            "description": "Check PDRN serum stock, reorder if below threshold",
            "priority": 2,
            "priority_label": "medium",
            "due_date": datetime.now(pytz.timezone(BUSINESS_TIMEZONE)).strftime("%Y-%m-%d"),
            "category": "inventory",
            "source": "demo"
        },
        {
            "id": "task_003",
            "title": "Respond to WhatsApp inquiries",
            "description": "3 unread messages from potential clients",
            "priority": 3,
            "priority_label": "medium",
            "due_date": datetime.now(pytz.timezone(BUSINESS_TIMEZONE)).strftime("%Y-%m-%d"),
            "category": "communications",
            "source": "demo"
        }
    ][:limit]


# ==================== TIME SERVICE ====================

def get_current_time() -> Dict[str, Any]:
    """Get current time information for the business timezone."""
    tz = pytz.timezone(BUSINESS_TIMEZONE)
    now = datetime.now(tz)
    
    hour = now.hour
    if 5 <= hour < 12:
        greeting = "Good morning"
        period = "morning"
    elif 12 <= hour < 17:
        greeting = "Good afternoon"
        period = "afternoon"
    elif 17 <= hour < 21:
        greeting = "Good evening"
        period = "evening"
    else:
        greeting = "Good night"
        period = "night"
    
    return {
        "current_time": now.strftime("%I:%M %p"),
        "current_time_24h": now.strftime("%H:%M"),
        "date": now.strftime("%A, %B %d, %Y"),
        "date_short": now.strftime("%Y-%m-%d"),
        "day_of_week": now.strftime("%A"),
        "greeting": greeting,
        "period": period,
        "timezone": BUSINESS_TIMEZONE,
        "timestamp": now.isoformat()
    }


# ==================== SENTIMENT LAYER ====================

class SentimentTone:
    """
    Sentiment Layer for Envoy Agent narration.
    
    Adjusts tone based on task load:
    - Light (0-2 tasks): Casual, upbeat
    - Moderate (3-5 tasks): Professional, efficient
    - Heavy (>5 tasks): "Old Money" composed, encouraging
    """
    
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    
    @staticmethod
    def assess(task_count: int) -> str:
        if task_count <= 2:
            return SentimentTone.LIGHT
        elif task_count <= 5:
            return SentimentTone.MODERATE
        else:
            return SentimentTone.HEAVY
    
    @staticmethod
    def get_greeting_prefix(tone: str, base_greeting: str) -> str:
        if tone == SentimentTone.HEAVY:
            return f"{base_greeting}. Take a breath - we shall address each matter with precision"
        elif tone == SentimentTone.MODERATE:
            return f"{base_greeting}! A productive day awaits"
        else:
            return f"{base_greeting}!"
    
    @staticmethod
    def get_task_intro(tone: str, task_count: int) -> str:
        if tone == SentimentTone.HEAVY:
            return (
                f"You have {task_count} matters requiring attention. "
                f"Remember: one deliberate step at a time. "
                f"Let us begin with the most pressing"
            )
        elif tone == SentimentTone.MODERATE:
            return f"You have {task_count} tasks on your agenda today"
        else:
            if task_count == 0:
                return "Your schedule is clear"
            elif task_count == 1:
                return "Just one item on your list today"
            else:
                return f"You have {task_count} items to address"
    
    @staticmethod
    def get_closing(tone: str, task_count: int) -> str:
        if tone == SentimentTone.HEAVY:
            return (
                "Approach each task as an opportunity, not an obligation. "
                "Excellence is not rushed - it is cultivated."
            )
        elif tone == SentimentTone.MODERATE:
            return "You've got this. Focus on what matters most."
        else:
            if task_count == 0:
                return "Enjoy your day."
            else:
                return "Have a great day!"
    
    @staticmethod
    def get_weather_transition(tone: str) -> str:
        if tone == SentimentTone.HEAVY:
            return "The conditions outside"
        elif tone == SentimentTone.MODERATE:
            return "Weather-wise"
        else:
            return "It's"


def build_narration_with_sentiment(
    time_data: Dict[str, Any],
    weather_data: Dict[str, Any],
    pending_tasks: List[Dict[str, Any]],
    total_task_count: int = None
) -> Dict[str, Any]:
    """Build narration text with Sentiment Layer applied."""
    task_count = total_task_count if total_task_count is not None else len(pending_tasks)
    tone = SentimentTone.assess(task_count)
    
    greeting_prefix = SentimentTone.get_greeting_prefix(tone, time_data['greeting'])
    weather_transition = SentimentTone.get_weather_transition(tone)
    
    if tone == SentimentTone.HEAVY:
        weather_segment = (
            f"{weather_transition}: {weather_data['temperature']}C, "
            f"{weather_data['description']} in {weather_data['location']}."
        )
    else:
        weather_segment = (
            f"{weather_transition} {time_data['current_time']}, "
            f"currently {weather_data['temperature']}C and {weather_data['description']} "
            f"in {weather_data['location']}."
        )
    
    task_intro = SentimentTone.get_task_intro(tone, task_count)
    
    if pending_tasks:
        task_titles = [t.get("title", "Unknown task") for t in pending_tasks[:3]]
        
        if tone == SentimentTone.HEAVY:
            task_list = ". Then, ".join(task_titles[:2])
            if len(task_titles) > 2:
                remaining = task_count - 2
                task_segment = f"{task_intro}: {task_list}. And {remaining} more items thereafter."
            else:
                task_segment = f"{task_intro}: {task_list}."
        else:
            task_list = ", ".join(task_titles)
            task_segment = f"{task_intro}: {task_list}."
    else:
        task_segment = task_intro + "."
    
    closing = SentimentTone.get_closing(tone, task_count)
    
    if tone == SentimentTone.HEAVY:
        narration = f"{greeting_prefix}. {weather_segment} {task_segment} {closing}"
    else:
        narration = f"{greeting_prefix} {weather_segment} {task_segment} {closing}"
    
    return {
        "narration": narration,
        "tone": tone,
        "tone_label": {
            SentimentTone.LIGHT: "casual",
            SentimentTone.MODERATE: "professional", 
            SentimentTone.HEAVY: "old_money_composed"
        }.get(tone, "neutral"),
        "task_load": {
            "count": task_count,
            "level": "light" if task_count <= 2 else "moderate" if task_count <= 5 else "heavy",
            "stress_mitigation_active": tone == SentimentTone.HEAVY
        }
    }


# ==================== MAIN MORNING BRIEF ENDPOINTS ====================

@router.get("/morning-brief")
async def get_morning_brief(
    business_id: str = Query("default", description="Business ID for task context"),
    location: str = Query(DEFAULT_LOCATION, description="Location for weather"),
    task_limit: int = Query(10, ge=1, le=20, description="Number of pending tasks to fetch")
):
    """
    Get aggregated morning brief for the Envoy Agent to narrate.
    
    Includes Sentiment Layer:
    - Light load (0-2 tasks): Casual, upbeat tone
    - Moderate load (3-5 tasks): Professional, efficient tone
    - Heavy load (>5 tasks): "Old Money" composed tone for stress management
    """
    import asyncio
    
    time_data = get_current_time()
    weather_task = fetch_weather(location)
    tasks_task = fetch_pending_tasks(business_id, task_limit)
    
    weather_data, pending_tasks = await asyncio.gather(weather_task, tasks_task)
    
    narration_data = build_narration_with_sentiment(
        time_data=time_data,
        weather_data=weather_data,
        pending_tasks=pending_tasks,
        total_task_count=len(pending_tasks)
    )
    
    return {
        "brief": {
            "narration": narration_data["narration"],
            "tone": narration_data["tone"],
            "tone_label": narration_data["tone_label"],
            "stress_mitigation_active": narration_data["task_load"]["stress_mitigation_active"],
            "generated_at": datetime.now(timezone.utc).isoformat()
        },
        "time": time_data,
        "weather": weather_data,
        "tasks": {
            "count": len(pending_tasks),
            "load_level": narration_data["task_load"]["level"],
            "items": pending_tasks,
            "summary": [t.get("title", "Unknown") for t in pending_tasks[:5]]
        },
        "sentiment": narration_data["task_load"],
        "metadata": {
            "business_id": business_id,
            "location": location,
            "sources": {
                "weather": weather_data.get("source", "unknown"),
                "tasks": pending_tasks[0].get("source", "database") if pending_tasks else "none"
            }
        }
    }


@router.get("/morning-brief/narration")
async def get_narration_only(
    business_id: str = Query("default"),
    location: str = Query(DEFAULT_LOCATION),
    task_limit: int = Query(10, ge=1, le=20)
):
    """
    Get just the narration text for TTS with Sentiment Layer.
    Lightweight endpoint for voice-only use cases.
    """
    brief = await get_morning_brief(business_id, location, task_limit)
    
    return {
        "narration": brief["brief"]["narration"],
        "greeting": brief["time"]["greeting"],
        "tone": brief["brief"]["tone"],
        "tone_label": brief["brief"]["tone_label"],
        "stress_mitigation_active": brief["brief"]["stress_mitigation_active"],
        "task_count": brief["tasks"]["count"],
        "generated_at": brief["brief"]["generated_at"]
    }


# ==================== TASK MANAGEMENT ENDPOINTS ====================

@router.post("/tasks")
async def create_task(
    business_id: str,
    title: str,
    description: str = "",
    priority: int = Query(2, ge=1, le=5),
    category: str = "general"
):
    """
    Create a new task (stored in Redis and MongoDB).
    
    Priority levels: 1=Critical, 2=High, 3=Medium, 4=Low, 5=Backlog
    """
    import json
    
    task = {
        "id": f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "business_id": business_id,
        "title": title,
        "description": description,
        "priority": priority,
        "priority_label": ["critical", "high", "medium", "low", "backlog"][priority - 1],
        "category": category,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "due_date": None
    }
    
    try:
        import redis.asyncio as redis
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)
        
        task_key = f"aurem:tasks:{business_id}"
        await r.zadd(task_key, {json.dumps(task): priority})
        await r.close()
        
    except Exception as e:
        logger.warning(f"[MorningBrief] Redis task store failed: {e}")
    
    try:
        db = get_db()
        await db["aurem_tasks"].insert_one(task.copy())
    except Exception as e:
        logger.warning(f"[MorningBrief] MongoDB task store failed: {e}")
    
    return {"status": "created", "task": task}


@router.delete("/tasks/{task_id}")
async def complete_task(task_id: str, business_id: str = Query(...)):
    """Mark a task as complete (removes from pending)."""
    try:
        import redis.asyncio as redis
        import json
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        r = redis.from_url(redis_url)
        
        task_key = f"aurem:tasks:{business_id}"
        
        all_tasks = await r.zrange(task_key, 0, -1)
        for task_data in all_tasks:
            task = json.loads(task_data)
            if task.get("id") == task_id:
                await r.zrem(task_key, task_data)
                break
        
        await r.close()
        
    except Exception as e:
        logger.warning(f"[MorningBrief] Redis task remove failed: {e}")
    
    try:
        db = get_db()
        await db["aurem_tasks"].update_one(
            {"id": task_id, "business_id": business_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
        )
    except Exception as e:
        logger.warning(f"[MorningBrief] MongoDB task update failed: {e}")
    
    return {"status": "completed", "task_id": task_id}


# ==================== ARCHITECTURE DOCUMENTATION ENDPOINTS ====================

@router.get("/architecture")
async def get_architecture_overview():
    """
    Get AUREM platform architecture overview.
    
    Executive-level documentation for stakeholders showing:
    - Platform capabilities across all phases
    - OODA Loop architecture
    - Omnichannel integration specs
    - ROI metrics and cost savings
    """
    return {
        "platform": "AUREM",
        "tagline": "Autonomous Business Operating System",
        "version": "2.0",
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "executive_summary": {
            "description": "AUREM is an Autonomous Business Operating System that transforms enterprise customer interactions through AI-powered decision making.",
            "core_capabilities": [
                "Thinking - OODA Loop reasoning framework",
                "Hearing - Omnichannel voice and messaging",
                "Acting - Calendar bookings, payments, emails",
                "Collaborating - Agent-to-Agent protocols",
                "Learning - Knowledge base auto-updates"
            ],
            "cost_impact": "97% reduction vs human agents ($0.45/call AI vs $15/call human)"
        },
        "phases": {
            "phase_1": {
                "name": "Brain Orchestrator",
                "description": "OODA Loop (Observe, Orient, Decide, Act) as core reasoning framework",
                "components": ["Scout Agent", "Architect Agent", "Envoy Agent"],
                "memory": "Redis-powered Hydrated Memory for customer context persistence"
            },
            "phase_2": {
                "name": "Omnichannel Sensory Layer",
                "description": "Voice, WhatsApp, Email, Web Chat unified into single Command Center",
                "components": ["Vapi + Vobiz Voice", "WhatsApp Cloud API", "Gmail Integration", "Unified Inbox"]
            },
            "phase_3": {
                "name": "Action Engine",
                "description": "Real-world execution through integrated tools",
                "tools": ["Google Calendar", "Stripe", "Gmail", "Agent-Reach (Zero-API)"],
                "agent_reach": {
                    "philosophy": "Zero-API Social Intelligence",
                    "cost": "$0/request",
                    "capabilities": ["Twitter Search", "Reddit Search", "YouTube Transcripts", "Web Reader"]
                }
            },
            "phase_4": {
                "name": "Observability",
                "description": "Brain Debugger for transparent AI decision-making",
                "features": ["OODA Trace Visualization", "Decision Audit Trail", "Real-time Telemetry"]
            },
            "phase_5": {
                "name": "Executive Interface",
                "description": "High-level business intelligence tools",
                "features": ["Morning Brief", "Voice Analytics Dashboard", "ROI Tracking"]
            }
        },
        "operational_flow": [
            {"stage": 1, "name": "Ingest", "action": "Receive via Voice/WhatsApp/Email", "component": "Omnichannel Gateway"},
            {"stage": 2, "name": "Observe", "action": "Identify intent, fetch customer profile", "component": "Scout Agent + Redis"},
            {"stage": 3, "name": "Orient", "action": "Contextualize against Knowledge Base", "component": "Architect Agent"},
            {"stage": 4, "name": "Decide", "action": "Select tool or A2A handoff", "component": "Brain Orchestrator"},
            {"stage": 5, "name": "Act", "action": "Execute and respond", "component": "Envoy Agent + Action Engine"},
            {"stage": 6, "name": "Audit", "action": "Log OODA trace", "component": "Brain Debugger"}
        ],
        "roadmap": {
            "p0": ["Configure live Vapi credentials", "Configure Exa API for Reddit"],
            "p1": ["YouTube Knowledge Importer", "Voice recording playback", "Multi-language support"],
            "p2": ["Full A2A protocol", "ROI Calculator widget", "Competitor monitoring alerts"]
        },
        "documentation_url": "/app/memory/AUREM_ARCHITECTURE.md"
    }


@router.get("/architecture/roi")
async def get_roi_calculator():
    """
    Get detailed ROI Calculator metrics.
    
    Based on Phase 8.2 Voice Analytics data:
    - 847 total calls processed
    - 38% action rate (booking/payment conversion)
    - 97% cost reduction vs human agents
    """
    # Base metrics from Phase 8.2
    total_calls = 847
    action_rate = 0.38
    avg_duration_seconds = 142
    
    # Cost comparison
    human_cost_per_call = 15.00
    ai_cost_per_call = 0.45
    savings_per_call = human_cost_per_call - ai_cost_per_call
    savings_percent = round((savings_per_call / human_cost_per_call) * 100)
    
    # Calculate actual savings
    actual_savings = total_calls * savings_per_call
    successful_actions = int(total_calls * action_rate)
    
    # Projected monthly/annual (assuming current volume scales)
    monthly_projection = 1000  # calls
    monthly_human_cost = monthly_projection * human_cost_per_call
    monthly_ai_cost = monthly_projection * ai_cost_per_call
    monthly_savings = monthly_human_cost - monthly_ai_cost
    annual_savings = monthly_savings * 12
    
    return {
        "roi_calculator": {
            "title": "AUREM ROI Analysis",
            "subtitle": "Cost Savings vs Human Agents",
            "current_metrics": {
                "total_calls": total_calls,
                "action_rate": f"{int(action_rate * 100)}%",
                "successful_conversions": successful_actions,
                "avg_call_duration": f"{avg_duration_seconds}s",
                "total_handle_time": f"{round(total_calls * avg_duration_seconds / 3600, 1)} hours"
            },
            "cost_comparison": {
                "human_cost_per_call": human_cost_per_call,
                "ai_cost_per_call": ai_cost_per_call,
                "savings_per_call": savings_per_call,
                "savings_percent": savings_percent
            },
            "actual_savings": {
                "calls_processed": total_calls,
                "total_savings": round(actual_savings, 2),
                "human_equivalent_cost": round(total_calls * human_cost_per_call, 2),
                "aurem_cost": round(total_calls * ai_cost_per_call, 2)
            },
            "projections": {
                "monthly": {
                    "calls": monthly_projection,
                    "human_cost": monthly_human_cost,
                    "ai_cost": monthly_ai_cost,
                    "savings": monthly_savings
                },
                "annual": {
                    "calls": monthly_projection * 12,
                    "human_cost": monthly_human_cost * 12,
                    "ai_cost": monthly_ai_cost * 12,
                    "savings": annual_savings
                }
            },
            "summary": {
                "headline": f"${int(annual_savings):,} Annual Savings",
                "description": f"AUREM delivers a {savings_percent}% cost reduction by handling {monthly_projection} calls/month at ${ai_cost_per_call}/call vs ${human_cost_per_call}/call for human agents.",
                "key_benefit": "Autonomous 24/7 operation with consistent quality"
            }
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/architecture/a2a")
async def get_a2a_specs():
    """
    Get Agent-to-Agent (A2A) Communication Protocol specifications.
    
    Documents how different business agents collaborate:
    - ReRoots Skincare Agent
    - TJ Auto Clinic Agent
    - Finance Agent (Shared)
    - Research Agent (Agent-Reach)
    """
    return {
        "a2a_protocol": {
            "title": "AUREM Agent-to-Agent Communication",
            "description": "Multi-agent collaboration framework enabling specialized AI agents to work together as a unified swarm",
            "version": "1.0",
            "agents": {
                "reroots_skincare": {
                    "name": "ReRoots Skincare Agent",
                    "domain": "Beauty & skincare consultations",
                    "knowledge_base": ["PDRN technology", "Skincare routines", "Product catalog", "Treatment pricing"],
                    "capabilities": ["Booking consultations", "Product recommendations", "Treatment education"],
                    "can_hire": ["finance_agent", "research_agent"]
                },
                "tj_auto": {
                    "name": "TJ Auto Clinic Agent",
                    "domain": "Automotive service & repairs",
                    "knowledge_base": ["GMC/Chevy diagnostics", "Service pricing", "Parts catalog", "Maintenance schedules"],
                    "capabilities": ["Service appointments", "Diagnostic inquiries", "Quote generation"],
                    "can_hire": ["finance_agent", "research_agent"]
                },
                "finance_agent": {
                    "name": "Finance Agent",
                    "domain": "Payment processing & invoicing",
                    "knowledge_base": ["Stripe integration", "Invoice templates", "Payment policies"],
                    "capabilities": ["Create payment links", "Generate invoices", "Process refunds"],
                    "shared_by": ["reroots_skincare", "tj_auto"]
                },
                "research_agent": {
                    "name": "Research Agent (Agent-Reach)",
                    "domain": "Market intelligence & competitor analysis",
                    "knowledge_base": ["Twitter/X search", "Reddit threads", "YouTube transcripts"],
                    "capabilities": ["Social listening", "Competitor monitoring", "Trend analysis"],
                    "shared_by": ["reroots_skincare", "tj_auto"]
                }
            },
            "handshake_protocol": {
                "description": "When one agent needs capabilities from another",
                "flow": [
                    {"step": 1, "action": "Requesting agent identifies need", "example": "Skincare agent needs payment link"},
                    {"step": 2, "action": "A2A request created with context", "example": "Task: create_payment_link, Amount: $299"},
                    {"step": 3, "action": "Target agent receives and validates", "example": "Finance agent checks permissions"},
                    {"step": 4, "action": "Target agent executes task", "example": "Stripe link generated"},
                    {"step": 5, "action": "Result returned via callback", "example": "Payment URL sent back to skincare agent"},
                    {"step": 6, "action": "Original agent continues conversation", "example": "Customer receives payment link"}
                ],
                "example_request": {
                    "from_agent": "reroots_skincare",
                    "to_agent": "finance_agent",
                    "task": "create_payment_link",
                    "params": {
                        "amount": 299.00,
                        "currency": "CAD",
                        "description": "PDRN Facial Treatment",
                        "customer_email": "client@example.com"
                    },
                    "callback": "reroots_skincare.handle_payment_result",
                    "priority": "high",
                    "timeout_ms": 5000
                },
                "example_response": {
                    "status": "success",
                    "from_agent": "finance_agent",
                    "to_agent": "reroots_skincare",
                    "result": {
                        "payment_link": "https://pay.stripe.com/c/pay/xxx",
                        "expires_at": "2026-04-09T14:30:00Z",
                        "invoice_id": "inv_001"
                    },
                    "execution_time_ms": 1234
                }
            },
            "benefits": [
                "Specialized expertise - Each agent masters its domain",
                "Shared resources - Finance/Research available to all",
                "Scalability - Add new agents without rewiring",
                "Auditability - Every A2A request is logged"
            ]
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/architecture/flow-chart")
async def get_flow_chart():
    """
    Get AUREM operational lifecycle flow chart data.
    
    Provides structured data for rendering the OODA flow visualization.
    """
    return {
        "flow_chart": {
            "title": "AUREM OPERATIONAL LIFECYCLE",
            "description": "Customer contact flows through the OODA loop to resolution",
            "stages": [
                {
                    "number": 1, 
                    "name": "INGEST", 
                    "description": "Receive customer contact",
                    "channels": ["Vapi Voice", "WhatsApp", "Email", "Web Chat"],
                    "output": "Raw message + metadata"
                },
                {
                    "number": 2, 
                    "name": "OBSERVE", 
                    "description": "Identify intent and fetch context",
                    "components": ["Scout Agent", "Intent Detection", "Redis Hydrate", "Customer Fetch"],
                    "output": "Customer context hydrated"
                },
                {
                    "number": 3, 
                    "name": "ORIENT", 
                    "description": "Contextualize against knowledge base",
                    "components": ["Architect Agent", "Knowledge Base", "PDRN/Auto KB", "Context Build"],
                    "output": "Decision framework built"
                },
                {
                    "number": 4, 
                    "name": "DECIDE", 
                    "description": "Select best action or handoff",
                    "components": ["Brain Orchestrator", "Tool Selection", "A2A Handoff", "Priority Queue"],
                    "output": "Action plan determined"
                },
                {
                    "number": 5, 
                    "name": "ACT", 
                    "description": "Execute and respond to customer",
                    "tools": ["Calendar", "Stripe", "Gmail", "WhatsApp", "Voice Response"],
                    "output": "Real-world execution complete"
                },
                {
                    "number": 6, 
                    "name": "AUDIT", 
                    "description": "Log decision trail for transparency",
                    "components": ["Brain Debugger", "OODA Trace", "Unified Inbox"],
                    "output": "Full audit trail recorded"
                }
            ],
            "connections": [
                {"from": 1, "to": 2, "label": "Message received"},
                {"from": 2, "to": 3, "label": "Intent + context"},
                {"from": 3, "to": 4, "label": "Decision framework"},
                {"from": 4, "to": 5, "label": "Action plan"},
                {"from": 5, "to": 6, "label": "Execution result"},
                {"from": 6, "to": "resolution", "label": "Customer satisfied"}
            ]
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/architecture/capability-matrix")
async def get_capability_matrix():
    """
    Get AUREM Capability Matrix for executive presentations.
    
    Maps each phase to its capabilities and business benefits.
    """
    return {
        "capability_matrix": {
            "title": "AUREM Capability Matrix",
            "description": "Phase-by-phase breakdown of platform capabilities",
            "matrix": [
                {
                    "phase": "I",
                    "name": "OODA Loop",
                    "capability": "Real-time AI decision making",
                    "benefit": "Consistent, high-quality responses vs static scripts",
                    "status": "LIVE"
                },
                {
                    "phase": "II",
                    "name": "Omnichannel",
                    "capability": "WhatsApp, Voice, and Email in one Unified Inbox",
                    "benefit": "Single view of all customer interactions",
                    "status": "LIVE"
                },
                {
                    "phase": "III",
                    "name": "Agent-Reach",
                    "capability": "Zero-cost internet research (Reddit/Twitter/YouTube)",
                    "benefit": "$0/request social intelligence vs $150+/month APIs",
                    "status": "LIVE"
                },
                {
                    "phase": "IV",
                    "name": "A2A Protocol",
                    "capability": "Multi-business collaboration (Skincare + Auto)",
                    "benefit": "Specialized agents working as unified swarm",
                    "status": "BETA"
                },
                {
                    "phase": "V",
                    "name": "Morning Brief",
                    "capability": "Proactive executive summary and task curation",
                    "benefit": "Start each day with AI-curated priorities",
                    "status": "LIVE"
                }
            ],
            "upcoming": [
                {
                    "name": "YouTube Knowledge Importer",
                    "description": "Auto-ingest video transcripts into knowledge base",
                    "priority": "P1"
                },
                {
                    "name": "Voice Recording Playback",
                    "description": "Review and analyze past voice interactions",
                    "priority": "P1"
                }
            ]
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
