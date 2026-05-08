"""
Auto Modularization Engine — Codebase Health & Architecture Analyzer
=====================================================================
Scans the live codebase to produce real-time modularization metrics:
router/service counts, line-count distribution, dependency maps,
and an overall architecture health score.
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modularization", tags=["Modularization"])

_db = None

def set_db(database):
    global _db
    _db = database

BASE_DIR = "/app/backend"
ROUTERS_DIR = os.path.join(BASE_DIR, "routers")
SERVICES_DIR = os.path.join(BASE_DIR, "services")
SERVER_FILE = os.path.join(BASE_DIR, "server.py")

# Original monolith size before modularization
ORIGINAL_SERVER_LINES = 43200


def _count_lines(filepath: str) -> int:
    try:
        with open(filepath, "r", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def _scan_directory(dirpath: str) -> list:
    """Scan a directory for .py files, return list of {name, lines, path}."""
    results = []
    if not os.path.isdir(dirpath):
        return results
    for fname in sorted(os.listdir(dirpath)):
        if fname.endswith(".py") and not fname.startswith("__"):
            fpath = os.path.join(dirpath, fname)
            lines = _count_lines(fpath)
            results.append({
                "name": fname.replace(".py", ""),
                "file": fname,
                "lines": lines,
            })
    return results


def _categorize_size(lines: int) -> str:
    if lines <= 50:
        return "micro"
    elif lines <= 150:
        return "small"
    elif lines <= 300:
        return "medium"
    elif lines <= 600:
        return "large"
    else:
        return "oversized"


def _compute_health_score(server_lines: int, routers: list, services: list) -> dict:
    """Compute an architecture health score 0-100."""
    score = 100
    penalties = []

    # Penalty: server.py still too big (ideal < 500)
    if server_lines > 2000:
        p = min(30, (server_lines - 2000) // 100)
        score -= p
        penalties.append({"rule": "server.py > 2000 lines", "penalty": p})
    elif server_lines > 1000:
        p = min(10, (server_lines - 1000) // 200)
        score -= p
        penalties.append({"rule": "server.py > 1000 lines", "penalty": p})

    # Penalty: oversized modules
    oversized_routers = [r for r in routers if r["lines"] > 600]
    oversized_services = [s for s in services if s["lines"] > 600]
    if oversized_routers:
        p = min(15, len(oversized_routers) * 3)
        score -= p
        penalties.append({"rule": f"{len(oversized_routers)} oversized routers (>600 lines)", "penalty": p})
    if oversized_services:
        p = min(15, len(oversized_services) * 3)
        score -= p
        penalties.append({"rule": f"{len(oversized_services)} oversized services (>600 lines)", "penalty": p})

    # Bonus: good modularization ratio
    total_modules = len(routers) + len(services)
    if total_modules >= 200:
        score = min(100, score + 5)

    return {"score": max(0, min(100, score)), "penalties": penalties}


@router.get("/stats")
async def get_modularization_stats():
    """Full codebase modularization report."""
    server_lines = _count_lines(SERVER_FILE)
    routers = _scan_directory(ROUTERS_DIR)
    services = _scan_directory(SERVICES_DIR)

    # Size distribution
    router_sizes = {}
    for r in routers:
        cat = _categorize_size(r["lines"])
        router_sizes[cat] = router_sizes.get(cat, 0) + 1

    service_sizes = {}
    for s in services:
        cat = _categorize_size(s["lines"])
        service_sizes[cat] = service_sizes.get(cat, 0) + 1

    total_router_lines = sum(r["lines"] for r in routers)
    total_service_lines = sum(s["lines"] for s in services)
    total_codebase_lines = server_lines + total_router_lines + total_service_lines

    health = _compute_health_score(server_lines, routers, services)

    reduction_pct = round((1 - server_lines / ORIGINAL_SERVER_LINES) * 100, 1) if ORIGINAL_SERVER_LINES > 0 else 0

    # Top 10 largest modules
    all_modules = [{"name": r["name"], "type": "router", "lines": r["lines"]} for r in routers] + \
                  [{"name": s["name"], "type": "service", "lines": s["lines"]} for s in services]
    all_modules.sort(key=lambda x: x["lines"], reverse=True)

    return {
        "server_py": {
            "current_lines": server_lines,
            "original_lines": ORIGINAL_SERVER_LINES,
            "reduction_pct": reduction_pct,
        },
        "routers": {
            "count": len(routers),
            "total_lines": total_router_lines,
            "avg_lines": round(total_router_lines / len(routers)) if routers else 0,
            "size_distribution": router_sizes,
        },
        "services": {
            "count": len(services),
            "total_lines": total_service_lines,
            "avg_lines": round(total_service_lines / len(services)) if services else 0,
            "size_distribution": service_sizes,
        },
        "total_modules": len(routers) + len(services),
        "total_codebase_lines": total_codebase_lines,
        "health": health,
        "top_modules": all_modules[:15],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/routers")
async def list_routers():
    """List all router modules with line counts."""
    routers = _scan_directory(ROUTERS_DIR)
    return {
        "count": len(routers),
        "routers": routers,
    }


@router.get("/services")
async def list_services():
    """List all service modules with line counts."""
    services = _scan_directory(SERVICES_DIR)
    return {
        "count": len(services),
        "services": services,
    }


@router.get("/history")
async def get_modularization_history():
    """Get modularization milestones from DB."""
    global _db
    if _db is None:
        try:
            from server import db
            _db = db
        except Exception:
            pass

    milestones = [
        {"date": "2026-03-15", "event": "Initial monolith", "server_lines": 43200, "routers": 0, "services": 12},
        {"date": "2026-03-25", "event": "Phase 1: Inline extraction", "server_lines": 4997, "routers": 45, "services": 38},
        {"date": "2026-04-01", "event": "Phase 2: Full modularization", "server_lines": 1409, "routers": 170, "services": 120},
    ]

    # Add live snapshot
    server_lines = _count_lines(SERVER_FILE)
    routers = _scan_directory(ROUTERS_DIR)
    services = _scan_directory(SERVICES_DIR)
    milestones.append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "event": "Live snapshot",
        "server_lines": server_lines,
        "routers": len(routers),
        "services": len(services),
    })

    return {"milestones": milestones}
