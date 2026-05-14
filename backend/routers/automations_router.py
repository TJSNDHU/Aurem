"""
AUREM Automation Engine Router
Handles workflow CRUD and execution
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/automations", tags=["AUREM Automations"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.get("/workflows")
async def get_workflows(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    workflows = []
    cursor = db.automations.find({"user_id": user_id}, {"_id": 0})
    async for wf in cursor:
        workflows.append(wf)

    return {"workflows": workflows}


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    trigger: str
    actions: List[str] = []
    category: Optional[str] = "General"


@router.post("/workflows")
async def create_workflow(data: WorkflowCreate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    import uuid
    workflow = {
        "id": f"wf-{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "name": data.name,
        "description": data.description,
        "trigger": data.trigger,
        "actions": data.actions,
        "category": data.category,
        "status": "paused",
        "runs_today": 0,
        "success_rate": 100,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.automations.insert_one(workflow)

    return {"success": True, "workflow_id": workflow["id"]}


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    result = await db.automations.delete_one({"user_id": user_id, "id": workflow_id})
    return {"success": True, "deleted": result.deleted_count > 0}
