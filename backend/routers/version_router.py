"""
routers/version_router.py — iter D-48

Cheap "what is deployed?" endpoint. Returns the most-recent git
commit (sha + summary + timestamp) and the explicit iter marker the
last code drop bumped. Useful when you need to confirm a production
deploy actually picked up your latest push.

  curl https://aurem.live/api/version
  → {"iter":"D-47","build":"...","commit":"abc1234",...}
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["version"])

# Bump this every iter. The frontend `index.html` <meta> tag must
# match. If they diverge, the deploy is mid-flight or stale.
ITER     = "D-57"
ITER_TS  = "2026-02-28"


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd="/app", stderr=subprocess.DEVNULL, timeout=2,
        ).decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def _build_info() -> dict:
    sha  = _git("rev-parse", "--short", "HEAD") or os.environ.get("BUILD_SHA", "")
    full = _git("rev-parse", "HEAD")            or os.environ.get("BUILD_SHA_FULL", "")
    msg  = _git("log", "-1", "--pretty=%s")     or ""
    ts   = _git("log", "-1", "--pretty=%cI")    or ""
    return {
        "commit_sha":       sha,
        "commit_sha_full":  full,
        "commit_message":   msg[:160],
        "commit_at":        ts,
    }


@router.get("/api/version")
async def version() -> dict:
    return {
        "iter":          ITER,
        "iter_date":     ITER_TS,
        "served_at":     datetime.now(timezone.utc).isoformat(),
        "build_sha":     os.environ.get("BUILD_SHA", "")[:12],
        **_build_info(),
    }
