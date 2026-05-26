"""
aurem_cto.routers.stacks — Gap 2 (iter D-33)
"""
from __future__ import annotations
from fastapi import APIRouter

from ..services.stacks import list_stacks, get_stack

router = APIRouter(prefix="/stacks", tags=["AUREM CTO Stacks"])


@router.get("")
async def list_route() -> dict:
    return {"stacks": list_stacks()}


@router.get("/{stack_id}")
async def get_route(stack_id: str) -> dict:
    s = get_stack(stack_id)
    if not s:
        return {"stack": None}
    return {"stack": s}
