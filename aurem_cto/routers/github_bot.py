"""
aurem_cto.routers.github_bot — P2 + P3 placeholder.

Pending build:
  • P2: auto-create private repo under customer account + enable branch
        protection enforced by the AUREM bot PAT.
  • P3: GitHub OAuth flow alongside the existing PAT path.

For now exposes a stub status endpoint so the frontend can detect the
module is loaded.
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from ..services.auth import current_dev

router = APIRouter(prefix="/github", tags=["AUREM CTO GitHub"])


@router.get("/status")
async def status(authorization: str = Header(None)) -> dict:
    me = await current_dev(authorization)
    return {
        "user_id":           me["user_id"],
        "bot_account":       "@aurem-cto-bot (pending P2)",
        "oauth_configured":  False,
        "p2_repo_create":    "pending",
        "p3_oauth_flow":     "pending",
    }
