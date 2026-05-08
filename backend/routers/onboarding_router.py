"""
Onboarding / Quick Start Wizard Router
Tracks tenant onboarding progress through 3 key activation steps
"""
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
import jwt
import os

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

ONBOARDING_STEPS = [
    {"id": "connect_crm", "title": "Connect Your CRM", "description": "Link HubSpot, Salesforce, Pipedrive, or Zoho to sync your contacts and deals automatically.", "nav_target": "crm-connect"},
    {"id": "setup_pipeline", "title": "Set Up Your Pipeline", "description": "Configure your sales stages and import your first deals to start tracking revenue.", "nav_target": "sales-pipeline"},
    {"id": "activate_ora", "title": "Activate ORA AI", "description": "Start a conversation with ORA to experience AI-powered business intelligence.", "nav_target": "ai-conversation"},
    {"id": "review_catalog", "title": "Review Service Catalog", "description": "Check the 17-service AUREM catalog, bundle rules, and platform MRR in the unified Command Hub.", "nav_target": "command-hub"},
    {"id": "configure_voice", "title": "Configure Voice Agent", "description": "Set up the AI inbound call handler (Retell AI). Add RETELL_API_KEY to enable live mode.", "nav_target": "command-hub"},
]


def _get_user_id(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = os.environ.get("JWT_SECRET", "")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("user_id") or payload.get("sub") or payload.get("id")
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.get("/status")
async def get_onboarding_status(request: Request):
    user_id = _get_user_id(request)
    db = get_db()

    record = await db.onboarding.find_one({"user_id": user_id}, {"_id": 0})

    if not record:
        record = {
            "user_id": user_id,
            "completed_steps": [],
            "dismissed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.onboarding.insert_one({**record})

    steps_with_status = []
    for step in ONBOARDING_STEPS:
        steps_with_status.append({
            **step,
            "completed": step["id"] in record.get("completed_steps", []),
        })

    total = len(ONBOARDING_STEPS)
    done = len(record.get("completed_steps", []))

    return {
        "steps": steps_with_status,
        "progress": done / total if total > 0 else 0,
        "completed_count": done,
        "total": total,
        "all_complete": done >= total,
        "dismissed": record.get("dismissed", False),
    }


@router.post("/complete-step")
async def complete_step(request: Request):
    user_id = _get_user_id(request)
    db = get_db()
    body = await request.json()
    step_id = body.get("step_id")

    if not step_id:
        raise HTTPException(400, "step_id required")

    valid_ids = [s["id"] for s in ONBOARDING_STEPS]
    if step_id not in valid_ids:
        raise HTTPException(400, "Invalid step_id")

    await db.onboarding.update_one(
        {"user_id": user_id},
        {
            "$addToSet": {"completed_steps": step_id},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"started_at": datetime.now(timezone.utc).isoformat(), "dismissed": False},
        },
        upsert=True,
    )

    return {"success": True, "step_id": step_id}


@router.post("/dismiss")
async def dismiss_wizard(request: Request):
    user_id = _get_user_id(request)
    db = get_db()

    await db.onboarding.update_one(
        {"user_id": user_id},
        {"$set": {"dismissed": True, "dismissed_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )

    return {"success": True}
