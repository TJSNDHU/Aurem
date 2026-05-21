"""
routers/customer_deploy_router.py — iter 326j Gap 2
═══════════════════════════════════════════════════════════════════════════
Receives deploy results from customer-side AUREM auto-deploy workflows.

When AUREM ships a fix to a customer's repo (via push_fix), the customer's
`.github/workflows/aurem_auto_deploy.yml` (shipped by ship_auto_deploy_workflow)
runs `pr_gate` + `deploy` jobs. The `deploy` job POSTs the result here:

  POST https://aurem.live/api/customer/deploy/report
  Authorization: Bearer <AUREM_API_KEY>
  Content-Type: application/json
  {"commit": "<sha>", "status": "success|failure|cancelled", "repo": "owner/repo"}

This closes the auto-fix → deploy → telemetry loop so founder sees
which customers shipped which fixes.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from services import github_deploy_service

logger = logging.getLogger(__name__)

router = APIRouter()

_db = None


def set_db(database) -> None:
    """Wire the DB at startup (mirrors all other AUREM routers)."""
    global _db
    _db = database
    github_deploy_service.set_db(database)


# ── Models ────────────────────────────────────────────────────────────
class DeployReport(BaseModel):
    commit:      str = Field(..., min_length=7, max_length=64)
    status:      str = Field(..., pattern="^(success|failure|cancelled)$")
    repo:        str = Field(..., min_length=3, max_length=200)
    deployed_at: Optional[str] = None


# ── Receiver endpoint ────────────────────────────────────────────────
@router.post("/api/customer/deploy/report")
async def receive_customer_deploy_report(
    body: DeployReport,
    authorization: Optional[str] = Header(default=None),
):
    """Receive a deploy outcome from a customer's GitHub Actions workflow.

    Auth: Bearer <AUREM_API_KEY> stamped into the customer's
    `github_connections.customer_api_key` when they connect.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    api_key = authorization.split(" ", 1)[1].strip()
    if not api_key:
        raise HTTPException(401, "empty bearer token")

    res = await github_deploy_service.record_customer_deploy_report(
        api_key=api_key,
        commit=body.commit,
        status=body.status,
        repo=body.repo,
        deployed_at=body.deployed_at,
    )
    if not res.get("ok"):
        # Soft-record happened → return 202 (accepted but unauthenticated).
        if res.get("soft_recorded"):
            raise HTTPException(202, res.get("error", "unauthorized"))
        raise HTTPException(403, res.get("error", "rejected"))
    return res


# ── Admin: list recent deploys ───────────────────────────────────────
@router.get("/api/admin/customer-deploys")
async def list_customer_deploys(limit: int = 50):
    """Founder-visible list of all customer deploy reports."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit), 200))
    out = []
    async for d in _db.github_deployments.find(
        {}, {"_id": 0, "deployment_id": 1, "tenant_id": 1, "repo": 1,
             "commit": 1, "status": 1, "deployed_at": 1, "unauth": 1,
             "received_at": 1}
    ).sort("received_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "deploys": out}
