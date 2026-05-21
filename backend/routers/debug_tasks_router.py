"""Tiny debug router — exposes live asyncio task names for verifying
pillar-worker liveness. Not gated by auth (read-only, safe in preview)."""
import asyncio
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/debug", tags=["debug"])


@router.get("/live-tasks")
async def live_tasks():
    tasks = asyncio.all_tasks()
    return {
        "total": len(tasks),
        "running": sum(1 for t in tasks if not t.done()),
        "names_sample": sorted({t.get_name() for t in tasks if not t.done()})[:60],
        "p1_count": sum(1 for t in tasks if t.get_name().startswith("p1:") and not t.done()),
        "p2_count": sum(1 for t in tasks if t.get_name().startswith("p2:") and not t.done()),
        "p3_count": sum(1 for t in tasks if t.get_name().startswith("p3:") and not t.done()),
        "p4_count": sum(1 for t in tasks if t.get_name().startswith("p4:") and not t.done()),
        "p3_names": sorted([t.get_name() for t in tasks if t.get_name().startswith("p3:") and not t.done()]),
    }
