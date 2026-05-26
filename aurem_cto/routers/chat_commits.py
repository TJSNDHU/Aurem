"""
aurem_cto.routers.chat_commits — P5 per-message rollback.

Lookup table linking chat message IDs to commit SHAs, with a rollback
endpoint that reverts the commit + redeploys.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(prefix="/chat-commits", tags=["AUREM CTO Chat Commits"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LinkBody(BaseModel):
    message_id: str = Field(..., min_length=4, max_length=128)
    commit_sha: str = Field(..., min_length=7, max_length=64)
    summary:    str = Field("", max_length=400)


@router.post("/link")
async def link_commit(body: LinkBody,
                      authorization: str = Header(None)) -> dict[str, Any]:
    """Called by the chat backend whenever a message triggers a code change."""
    me = await current_dev(authorization)
    db = require_db()
    await db.aurem_cto_chat_commits.update_one(
        {"user_id": me["user_id"], "message_id": body.message_id},
        {"$set": {
            "user_id":    me["user_id"],
            "message_id": body.message_id,
            "commit_sha": body.commit_sha,
            "summary":    body.summary,
            "rolled_back": False,
            "linked_at":  _now_iso(),
        }},
        upsert=True,
    )
    return {"ok": True}


@router.get("/by-message/{message_id}")
async def by_message(message_id: str,
                      authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_chat_commits.find_one(
        {"user_id": me["user_id"], "message_id": message_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "not_linked")
    return row


class RollbackBody(BaseModel):
    message_id: str = Field(..., min_length=4, max_length=128)


@router.post("/rollback")
async def rollback(body: RollbackBody,
                    authorization: str = Header(None)) -> dict[str, Any]:
    """Mark the rollback as initiated; the deploy router actually runs git revert."""
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_chat_commits.find_one(
        {"user_id": me["user_id"], "message_id": body.message_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(404, "not_linked")
    # The frontend follows up with POST /aurem-cto/deploy/run mode=revert_to sha=…
    return {
        "ok":          True,
        "message_id":  body.message_id,
        "commit_sha":  row["commit_sha"],
        "next_action": "POST /aurem-cto/deploy/run mode=revert_to",
    }
