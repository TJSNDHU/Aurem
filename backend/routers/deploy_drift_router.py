"""
Deploy Drift Router — iter 280.2
═══════════════════════════════════════════════════════════════════════

Surfaces the "preview-SHA vs prod-SHA" gap so operators can see at a glance
whether code committed via Save-to-GitHub is actually live on aurem.live, or
sitting uncommitted / unpushed / undeployed.

Why: AUREM own production deploy (aurem.live) is a MANUAL Emergent button
press — no webhook auto-trigger exists today. This router is the honest
observability layer that makes drift visible BEFORE customers hit stale code.

Endpoints:
  GET  /api/admin/deploy-drift           — full drift report (admin)
  GET  /api/admin/deploy-drift/health    — public probe

Semantics:
  prod_sha         : short SHA served by https://aurem.live/api/health
  preview_sha      : short SHA served by THIS pod (/app/.git HEAD)
  pending_commits  : git log prod_sha..preview_sha --oneline count
  oldest_drift_sec : seconds since the OLDEST pending commit landed on HEAD
  needs_deploy     : pending_commits > 0 AND oldest_drift_sec > THRESHOLD
"""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Header, HTTPException

from utils.admin_guard import verify_admin as _unified_verify_admin

router = APIRouter(prefix="/api/admin/deploy-drift", tags=["Deploy Drift"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"

PROD_HEALTH_URL = os.environ.get(
    "AUREM_PROD_HEALTH_URL", "https://aurem.live/api/health"
)

# Drift threshold: pending_commits older than this = needs_deploy=True.
DRIFT_THRESHOLD_SEC = int(os.environ.get("DEPLOY_DRIFT_THRESHOLD_SEC", "600"))  # 10 min

# Cache the expensive cross-pod HTTP + git log call.
_CACHE: Dict[str, Any] = {"ts": 0.0, "payload": None}
_CACHE_TTL_SEC = 60


def set_db(db) -> None:
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    return _unified_verify_admin(
        authorization,
        secret=_jwt_secret or os.environ.get("JWT_SECRET", ""),
        algorithm=_jwt_alg,
    )


def _strip_git_prefix(v: str) -> str:
    if not v:
        return ""
    return v[4:] if v.startswith("git-") else v


def _preview_sha() -> str:
    """Short SHA of HEAD on THIS pod (same logic as bootstrap.health_routes)."""
    sha = os.environ.get("AUREM_BUILD_SHA")
    if sha:
        return sha[:8]
    try:
        out = subprocess.run(
            ["git", "-C", "/app", "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    try:
        with open("/app/.build_sha", "r", encoding="utf-8") as fh:
            return fh.read().strip()[:8]
    except Exception:
        return ""


async def _fetch_prod_sha() -> Dict[str, Any]:
    """GET prod /api/health, return sha + raw reachable flag."""
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            r = await client.get(PROD_HEALTH_URL)
            if r.status_code == 200:
                data = r.json()
                return {
                    "reachable": True,
                    "sha": _strip_git_prefix(str(data.get("v", ""))),
                    "uptime_sec": data.get("uptime_seconds", 0),
                }
    except Exception as e:
        return {"reachable": False, "sha": "", "error": str(e)[:200]}
    return {"reachable": False, "sha": "", "error": f"HTTP {r.status_code}"}


def _pending_commits(prod_sha: str, preview_sha: str) -> List[Dict[str, Any]]:
    """git log prod_sha..preview_sha — returns parsed commit list (empty if same/missing)."""
    if not prod_sha or not preview_sha or prod_sha == preview_sha:
        return []
    try:
        out = subprocess.run(
            [
                "git", "-C", "/app", "log",
                f"{prod_sha}..{preview_sha}",
                "--pretty=format:%h|%s|%cI",
                "--no-merges",
                "-n", "50",
            ],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode != 0:
            return []
        commits: List[Dict[str, Any]] = []
        for line in out.stdout.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) != 3:
                continue
            commits.append({
                "sha": parts[0],
                "subject": parts[1][:180],
                "timestamp": parts[2],
            })
        return commits
    except Exception:
        return []


async def _compute_drift() -> Dict[str, Any]:
    prod = await _fetch_prod_sha()
    preview = _preview_sha()
    commits = _pending_commits(prod.get("sha", ""), preview)

    oldest_age = 0
    if commits:
        try:
            oldest_iso = commits[-1]["timestamp"]
            oldest_dt = datetime.fromisoformat(oldest_iso.replace("Z", "+00:00"))
            oldest_age = int((datetime.now(timezone.utc) - oldest_dt).total_seconds())
        except Exception:
            oldest_age = 0

    needs_deploy = len(commits) > 0 and oldest_age > DRIFT_THRESHOLD_SEC

    return {
        "prod_reachable": prod.get("reachable", False),
        "prod_sha": prod.get("sha", ""),
        "preview_sha": preview,
        "in_sync": (
            prod.get("reachable", False)
            and bool(prod.get("sha"))
            and prod.get("sha") == preview
        ),
        "pending_commits": len(commits),
        "oldest_drift_seconds": oldest_age,
        "needs_deploy": needs_deploy,
        "threshold_seconds": DRIFT_THRESHOLD_SEC,
        "recent_commits": commits[:10],
        "prod_error": prod.get("error"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_or_compute() -> Dict[str, Any]:
    now = time.time()
    if _CACHE["payload"] is not None and now - _CACHE["ts"] < _CACHE_TTL_SEC:
        return {**_CACHE["payload"], "cached": True}
    payload = await _compute_drift()
    _CACHE["ts"] = now
    _CACHE["payload"] = payload

    # Best-effort persistent history — skip if DB unset.
    if _db is not None:
        try:
            doc = {
                **payload,
                "cached": False,
                "computed_at_dt": datetime.now(timezone.utc),
            }
            doc.pop("cached_at", None)
            await _db.deploy_drift_history.insert_one(doc)
            # Trim to last 500 snapshots (non-blocking best-effort)
            cnt = await _db.deploy_drift_history.estimated_document_count()
            if cnt > 500:
                async for old in _db.deploy_drift_history.find(
                    {}, {"_id": 1}
                ).sort("computed_at_dt", 1).limit(cnt - 500):
                    await _db.deploy_drift_history.delete_one({"_id": old["_id"]})
        except Exception:
            pass

    return {**payload, "cached": False}


@router.get("")
async def deploy_drift(authorization: Optional[str] = Header(None)):
    """Full drift report — admin-only."""
    _verify_admin(authorization)
    return await _get_or_compute()


@router.get("/history")
async def deploy_drift_history(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    """Recent drift snapshots for trend analysis — admin-only."""
    _verify_admin(authorization)
    if _db is None:
        return {"history": [], "warning": "db_unset"}
    limit = max(1, min(int(limit or 50), 200))
    docs = []
    async for d in _db.deploy_drift_history.find(
        {}, {"_id": 0, "computed_at_dt": 0}
    ).sort("computed_at", -1).limit(limit):
        docs.append(d)
    return {"history": docs, "count": len(docs)}


@router.post("/invalidate")
async def deploy_drift_invalidate(authorization: Optional[str] = Header(None)):
    """Force-refresh the cache — admin-only."""
    _verify_admin(authorization)
    _CACHE["ts"] = 0.0
    _CACHE["payload"] = None
    return {"invalidated": True}


@router.get("/health")
async def deploy_drift_health():
    """Public probe — no auth. Returns only liveness, not drift details."""
    return {
        "status": "ok",
        "component": "deploy_drift",
        "prod_health_url": PROD_HEALTH_URL,
        "threshold_seconds": DRIFT_THRESHOLD_SEC,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
