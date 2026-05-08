"""
iter 282al-22 — Scrapling health router (Pillars chip).
"""
from __future__ import annotations

from fastapi import APIRouter
from typing import Any, Dict

router = APIRouter(prefix="/api/admin/scrapling", tags=["Scrapling"])


@router.get("/health")
async def scrapling_health() -> Dict[str, Any]:
    from services.scrapling_client import scrapling_health_check
    return await scrapling_health_check()
