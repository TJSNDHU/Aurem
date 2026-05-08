"""Deploy event logging — Iter 289.5

Captures the running build's commit SHA and records a `deploy_events` doc
once per (server boot × commit_sha) so the Founder Timeline can render
"View commit →" links and the weekly board digest can include deploy diff.

Idempotency:
  Each (commit_sha, boot_id) tuple inserts AT MOST ONE doc. boot_id is unique
  per process start, so a hot-reload triggers exactly one entry.
  If the same commit is deployed twice (e.g. rollback then re-deploy), each
  boot still records a separate event — that's the correct behaviour, the
  Timeline shows distinct deploys.
"""
from __future__ import annotations

import os
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("deploy-events")

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_REPO = os.environ.get("AUREM_GITHUB_REPO", "RerootsBeauty/ReRoots-")
_BOOT_ID = uuid.uuid4().hex[:12]


def _safe_run(cmd: list[str]) -> Optional[str]:
    try:
        out = subprocess.check_output(cmd, cwd=_REPO_ROOT, stderr=subprocess.DEVNULL, timeout=4)
        return out.decode().strip() or None
    except Exception:
        return None


def get_current_commit() -> dict:
    """Return {commit_sha, branch, message, author, timestamp_iso} for HEAD."""
    sha = _safe_run(["git", "rev-parse", "HEAD"]) or os.environ.get("AUREM_DEPLOY_COMMIT")
    branch = _safe_run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or os.environ.get("AUREM_DEPLOY_BRANCH", "main")
    message = _safe_run(["git", "log", "-1", "--pretty=%s"]) or ""
    author = _safe_run(["git", "log", "-1", "--pretty=%an"]) or ""
    ts = _safe_run(["git", "log", "-1", "--pretty=%cI"]) or None
    return {
        "commit_sha": sha,
        "branch": branch,
        "commit_message": message[:240],
        "commit_author": author,
        "commit_timestamp": ts,
    }


async def log_deploy_event(db, *, trigger: str = "boot", extra: Optional[dict] = None) -> Optional[dict]:
    """Insert a deploy_events doc once per (commit_sha, boot_id).

    Returns the inserted document (without _id) on success, None otherwise.
    """
    if db is None:
        return None
    info = get_current_commit()
    if not info.get("commit_sha"):
        logger.info("[deploy-log] no commit sha resolvable — skip")
        return None

    doc = {
        "trigger": trigger,
        "branch": info["branch"],
        "commit": info["commit_sha"],          # legacy field used elsewhere
        "commit_sha": info["commit_sha"],
        "commit_message": info["commit_message"],
        "commit_author": info["commit_author"],
        "commit_timestamp": info["commit_timestamp"],
        "repo": _DEFAULT_REPO,
        "boot_id": _BOOT_ID,
        "host": os.environ.get("HOSTNAME", ""),
        "env": os.environ.get("AUREM_ENV", "preview"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    try:
        # Idempotency only for trigger='boot' (prevents hot-reload duplicates).
        # Explicit CI/manual/webhook triggers are always recorded.
        if trigger == "boot":
            existing = await db.deploy_events.find_one(
                {"commit_sha": doc["commit_sha"], "boot_id": _BOOT_ID, "trigger": "boot"},
                {"_id": 1},
            )
            if existing:
                return None
        await db.deploy_events.insert_one(dict(doc))   # copy to avoid Mongo mutation
        logger.info(f"[deploy-log] recorded {info['commit_sha'][:7]} ({info['branch']}) trigger={trigger}")
        return {k: v for k, v in doc.items() if k != "_id"}
    except Exception as e:
        logger.warning(f"[deploy-log] insert failed: {e}")
        return None
