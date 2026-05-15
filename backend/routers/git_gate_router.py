"""
Git Commit Gate Admin Router — iter 322er
==========================================
Founder approval workflow for every ORA-proposed commit.

ORA can write files via `safe_edit` but CANNOT commit. To get a commit
into history, ORA calls the `propose_commit` ora_tool, which records a
proposal in `ora_commit_proposals`. The founder reviews each proposal in
the /admin/git-gate UI and clicks approve or reject. This router is
the ONLY place that runs the actual `git commit`.

Endpoints (under /api/admin/git-gate):
  GET   /proposals?status=pending|approved|rejected   list (newest first)
  GET   /proposals/{id}                               full diff
  POST  /proposals/{id}/approve                       runs real `git commit`
  POST  /proposals/{id}/reject?reason=...             revert files from backups
  GET   /history?limit=20                             all decisions
  GET   /summary                                      counts (pending/approved/rejected)

Auth: JWT bearer (any signed admin token).
"""
from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/git-gate", tags=["git-commit-gate"])


def _verify_token(authorization: Optional[str] = None) -> str:
    """Bug-fix 141 — was validating JWT signature only; any authenticated
    user could approve git proposals → run real `git commit` on production.
    Now requires admin/super-admin claim, role, or whitelisted email."""
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    is_admin = (
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
        or is_admin_email(payload.get("email"))
    )
    if not is_admin:
        raise HTTPException(403, "Admin access required (git operations)")
    return payload.get("email") or payload.get("user_id") or payload.get("sub") or "unknown"


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── List + retrieve ────────────────────────────────────────────────────

@router.get("/summary")
async def summary(authorization: Optional[str] = Header(None)):
    """Tile-style counts for the cockpit landing."""
    _verify_token(authorization)
    db = _get_db()
    pending = await db.ora_commit_proposals.count_documents({"status": "pending"})
    approved = await db.ora_commit_proposals.count_documents({"status": "approved"})
    rejected = await db.ora_commit_proposals.count_documents({"status": "rejected"})
    total = pending + approved + rejected
    return {
        "ok": True,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "total": total,
        "approval_rate": round(approved / max(total - pending, 1) * 100, 1) if (approved + rejected) else None,
    }


@router.get("/proposals")
async def list_proposals(
    status: str = Query("pending", regex="^(pending|approved|rejected|all)$"),
    limit: int = Query(30, ge=1, le=200),
    authorization: Optional[str] = Header(None),
):
    """List proposals filtered by status. Newest first."""
    _verify_token(authorization)
    db = _get_db()
    q: dict = {} if status == "all" else {"status": status}
    rows = []
    async for r in (
        db.ora_commit_proposals.find(q, {"diff": 0}).sort("proposed_at", -1).limit(limit)
    ):
        r.pop("_id", None)
        rows.append(r)
    total = await db.ora_commit_proposals.count_documents(q)
    return {"ok": True, "status": status, "total": total, "rows": rows}


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str,
                        authorization: Optional[str] = Header(None)):
    """Full proposal with diff."""
    _verify_token(authorization)
    db = _get_db()
    doc = await db.ora_commit_proposals.find_one({"id": proposal_id})
    if not doc:
        raise HTTPException(404, f"proposal not found: {proposal_id}")
    doc.pop("_id", None)
    return {"ok": True, "proposal": doc}


# ── Decide ─────────────────────────────────────────────────────────────

class DecisionRequest(BaseModel):
    note: str = Field("", max_length=500)


def _run_git(*cmd: str, timeout: int = 20) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git", *cmd],
        capture_output=True, text=True, timeout=timeout, cwd="/app",
    )
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def _ensure_git_identity() -> None:
    """Set git author identity so `git commit` doesn't fail in fresh containers."""
    for key, val in (
        ("user.email", "ora@aurem.live"),
        ("user.name",  "ORA (Sovereign CTO)"),
    ):
        try:
            r = subprocess.run(
                ["git", "config", "--local", key],
                capture_output=True, text=True, timeout=5, cwd="/app",
            )
            if not (r.stdout or "").strip():
                subprocess.run(
                    ["git", "config", "--local", key, val],
                    capture_output=True, text=True, timeout=5, cwd="/app",
                )
        except Exception:
            pass


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    req: DecisionRequest,
    authorization: Optional[str] = Header(None),
):
    """Run the real `git commit`. Stages exactly the files in the
    proposal, commits with the proposed title + body, then writes the
    resulting SHA back to the proposal doc.

    Idempotent: if the proposal is already approved, returns the
    existing SHA without re-committing.
    """
    actor = _verify_token(authorization)
    db = _get_db()
    doc = await db.ora_commit_proposals.find_one({"id": proposal_id})
    if not doc:
        raise HTTPException(404, f"proposal not found: {proposal_id}")
    if doc.get("status") == "approved":
        return {"ok": True, "already_approved": True,
                "commit_sha": doc.get("commit_sha"),
                "decided_at": doc.get("decided_at")}
    if doc.get("status") == "rejected":
        raise HTTPException(400, "proposal was rejected; create a new proposal")

    files = doc.get("files") or []
    if not files:
        raise HTTPException(400, "proposal has no files")

    # Stage exactly the files in the proposal
    try:
        _ensure_git_identity()
        rc, _, err = _run_git("add", "--", *files)
        if rc != 0:
            raise HTTPException(500, f"git add failed: {err[:240]}")

        # Compose commit message
        title = (doc.get("title") or "").strip()
        body = (doc.get("body") or "").strip()
        if body:
            full_msg = f"{title}\n\n{body}\n\nORA proposal: {proposal_id} — approved by {actor}"
        else:
            full_msg = f"{title}\n\nORA proposal: {proposal_id} — approved by {actor}"

        rc, out, err = _run_git("commit", "-m", full_msg)
        if rc != 0:
            # Roll back staged changes so the working tree stays clean
            _run_git("reset", "HEAD", "--")
            raise HTTPException(500, f"git commit failed: rc={rc} err={err[:240]}")

        # Capture SHA
        rc, sha, err = _run_git("rev-parse", "HEAD")
        if rc != 0:
            sha = ""
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "git commit timeout")
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {str(e)[:240]}")

    decision_doc = {
        "status":        "approved",
        "decided_at":    _now(),
        "decided_by":    actor,
        "decision_note": (req.note or "")[:500],
        "commit_sha":    sha,
    }
    await db.ora_commit_proposals.update_one(
        {"id": proposal_id}, {"$set": decision_doc}
    )
    return {"ok": True, "commit_sha": sha, "decided_by": actor,
            "proposal_id": proposal_id, **decision_doc}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    req: DecisionRequest,
    authorization: Optional[str] = Header(None),
):
    """Reject the proposal. Does NOT auto-revert the file edits — the
    files were written by safe_edit prior to propose_commit. To revert,
    follow the `revert_cmd` listed on each safe_edit backup.

    Use `?hard_reset=true` to ALSO unstage and reset the listed files
    to HEAD (effectively undo any edits made for this proposal).
    """
    actor = _verify_token(authorization)
    db = _get_db()
    doc = await db.ora_commit_proposals.find_one({"id": proposal_id})
    if not doc:
        raise HTTPException(404, f"proposal not found: {proposal_id}")
    if doc.get("status") != "pending":
        raise HTTPException(400, f"proposal already decided: {doc.get('status')}")

    note = (req.note or "")[:500]
    if not note.strip():
        raise HTTPException(400, "reject reason required in `note`")

    decision_doc = {
        "status":        "rejected",
        "decided_at":    _now(),
        "decided_by":    actor,
        "decision_note": note,
    }
    await db.ora_commit_proposals.update_one(
        {"id": proposal_id}, {"$set": decision_doc}
    )
    return {"ok": True, "proposal_id": proposal_id, **decision_doc}


@router.post("/proposals/{proposal_id}/hard-reset")
async def hard_reset_proposal(
    proposal_id: str,
    authorization: Optional[str] = Header(None),
):
    """Revert the working tree on the proposal's files back to HEAD.
    Use AFTER `/reject` if the founder wants the file edits undone.

    This runs `git checkout HEAD -- <file>` for each file in the
    proposal. Safe ONLY if the files were not edited further after the
    proposal was made.
    """
    actor = _verify_token(authorization)
    db = _get_db()
    doc = await db.ora_commit_proposals.find_one({"id": proposal_id})
    if not doc:
        raise HTTPException(404, f"proposal not found: {proposal_id}")
    files = doc.get("files") or []
    if not files:
        raise HTTPException(400, "proposal has no files to reset")
    try:
        rc, out, err = _run_git("checkout", "HEAD", "--", *files)
        if rc != 0:
            raise HTTPException(500, f"git checkout failed: {err[:240]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "git checkout timeout")
    await db.ora_commit_proposals.update_one(
        {"id": proposal_id},
        {"$set": {
            "hard_reset_at":    _now(),
            "hard_reset_by":    actor,
            "hard_reset_files": files,
        }},
    )
    return {"ok": True, "proposal_id": proposal_id, "reset_files": files,
            "reset_by": actor}


@router.get("/history")
async def history(
    limit: int = Query(30, ge=1, le=200),
    authorization: Optional[str] = Header(None),
):
    """Decided proposals (approved/rejected) — newest first."""
    _verify_token(authorization)
    db = _get_db()
    rows = []
    async for r in (
        db.ora_commit_proposals.find(
            {"status": {"$in": ["approved", "rejected"]}},
            {"diff": 0},
        ).sort("decided_at", -1).limit(limit)
    ):
        r.pop("_id", None)
        rows.append(r)
    return {"ok": True, "rows": rows, "count": len(rows)}


@router.get("/_/health")
async def health():
    db = _get_db()
    return {
        "ok": True,
        "scope": "git_commit_gate",
        "total_proposals": await db.ora_commit_proposals.count_documents({}),
        "pending":         await db.ora_commit_proposals.count_documents({"status": "pending"}),
    }
