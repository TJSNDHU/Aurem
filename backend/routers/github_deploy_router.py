"""
AUREM GitHub Deploy Router — Hybrid Fix Deployment
POST /api/github/connect — store customer GitHub token
POST /api/github/push-fix — create branch + commit + PR
GET  /api/github/pr-status — check if PR merged
GET  /api/github/status — connection status
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/github", tags=["GitHub Deploy"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _get_tenant(payload: dict) -> str:
    return payload.get("tenant_id") or payload.get("business_id") or "aurem_platform"


class ConnectRequest(BaseModel):
    token: str


@router.post("/connect")
async def connect_github(req: ConnectRequest, authorization: str = Header(None)):
    """Store customer GitHub token securely per tenant."""
    payload = await _auth(authorization)
    tenant_id = _get_tenant(payload)
    from services.github_deploy_service import connect_github as _connect, set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass
    result = await _connect(tenant_id, req.token)
    if not result.get("connected"):
        raise HTTPException(status_code=400, detail=result.get("error", "Connection failed"))
    return result


class PushFixRequest(BaseModel):
    repo: str
    fix_title: str
    fix_description: str
    file_path: str
    file_content: str
    base_branch: str = "main"


@router.post("/push-fix")
async def push_fix(req: PushFixRequest, authorization: str = Header(None)):
    """Create branch, commit fix, open PR in customer's repo."""
    payload = await _auth(authorization)
    tenant_id = _get_tenant(payload)
    from services.github_deploy_service import push_fix as _push, set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass
    result = await _push(
        tenant_id=tenant_id,
        repo=req.repo,
        fix_title=req.fix_title,
        fix_description=req.fix_description,
        file_path=req.file_path,
        file_content=req.file_content,
        base_branch=req.base_branch,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Push failed"))
    return result


@router.get("/pr-status")
async def pr_status(
    repo: Optional[str] = None,
    pr_number: Optional[int] = None,
    authorization: str = Header(None),
):
    """Check if PR has been merged."""
    payload = await _auth(authorization)
    tenant_id = _get_tenant(payload)
    from services.github_deploy_service import get_pr_status as _status, set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass
    result = await _status(tenant_id, pr_number=pr_number, repo=repo)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/status")
async def connection_status(authorization: str = Header(None)):
    """Check if tenant has GitHub connected."""
    payload = await _auth(authorization)
    tenant_id = _get_tenant(payload)
    from services.github_deploy_service import get_connection_status, set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass
    return await get_connection_status(tenant_id)
