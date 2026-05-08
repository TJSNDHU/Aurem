"""
Deploy Trigger Webhook — iter 287.1

Receives deploy signals from GitHub Actions (or any authorized caller) and:
  1. Verifies Bearer DEPLOY_SECRET
  2. Optionally gates on [auto-heal] marker in commit message
  3. Logs trigger to db.deploy_triggers (Truth-Sync: every attempt recorded)
  4. Background-runs `git pull origin main` + `supervisorctl restart backend`
  5. Returns 202 immediately with trigger_id — caller polls /api/admin/deploy/status/{id}

IMPORTANT HONESTY NOTES:
  • In the Emergent PREVIEW environment: git pull actually updates /app code,
    uvicorn --reload picks it up → effectively a hot-deploy.
  • In Emergent PRODUCTION: this endpoint logs the trigger and attempts pull,
    but the true "promote to prod" still requires clicking the Emergent Deploy
    button. We do NOT lie about this in the response — `deploy_kind` is set
    from env (`AUREM_ENV=preview` or `production`).
  • Secret rotation: DEPLOY_SECRET env var. Rotate monthly. GitHub Secrets mirror.

SECURITY:
  • Bearer token must match exactly (constant-time compare)
  • IP allowlist optional via DEPLOY_WEBHOOK_IP_ALLOWLIST (comma-separated)
  • Replay protection: trigger_id dedupe on (github_sha, github_run_id)
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("deploy_trigger")
router = APIRouter(prefix="/api/admin/deploy", tags=["deploy-trigger"])

_db: Any = None
TRIGGERS_COLLECTION = "deploy_triggers"


def set_db(db) -> None:
    global _db
    _db = db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verify_secret(authorization: Optional[str]) -> None:
    """Bearer DEPLOY_SECRET check, constant-time."""
    expected = (os.environ.get("DEPLOY_SECRET") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="DEPLOY_SECRET not configured on server — refusing trigger",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    provided = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid deploy secret")


def _check_ip_allowlist(request: Request) -> None:
    allowlist = (os.environ.get("DEPLOY_WEBHOOK_IP_ALLOWLIST") or "").strip()
    if not allowlist:
        return  # open to any IP (still secret-gated)
    allowed = [ip.strip() for ip in allowlist.split(",") if ip.strip()]
    client_ip = request.client.host if request.client else ""
    # Also check X-Forwarded-For (GitHub Actions runners' egress)
    fwd = request.headers.get("X-Forwarded-For", "")
    caller_ips = {client_ip} | {ip.strip() for ip in fwd.split(",") if ip.strip()}
    if not (caller_ips & set(allowed)):
        raise HTTPException(
            status_code=403,
            detail=f"IP {client_ip} not in allowlist",
        )


class DeployTriggerPayload(BaseModel):
    trigger:  str = "manual"        # "auto-heal" | "manual" | "scheduled"
    branch:   str = "main"
    commit:   Optional[str] = None  # full SHA
    message:  Optional[str] = None  # commit message (may include [auto-heal])
    actor:    Optional[str] = None  # github username
    run_id:   Optional[str] = None  # GitHub Actions run_id for replay dedup


async def _run_deploy_task(trigger_id: str, payload: DeployTriggerPayload) -> None:
    """Background task: git pull → supervisorctl restart backend.

    Records every step to db.deploy_triggers. Never raises — errors
    captured in the trigger document.
    """
    deploy_env = os.environ.get("AUREM_ENV", "preview").lower()
    log: list[dict] = []

    def _step(name: str, ok: bool, output: str = "", err: str = ""):
        log.append({
            "step": name, "ok": ok,
            "output": output[-500:] if output else "",
            "error": err[-500:] if err else "",
            "ts_iso": _now_iso(),
        })

    async def _sh(cmd: list[str], cwd: str = "/app", timeout: int = 60) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=cwd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, "", "TIMEOUT"
        return proc.returncode or 0, stdout.decode("utf-8", "ignore"), stderr.decode("utf-8", "ignore")

    # Step 1 — git fetch
    rc, out, err = await _sh(["git", "fetch", "origin", payload.branch])
    _step("git_fetch", rc == 0, out, err)

    # Step 2 — git pull (fast-forward only, no merge conflicts in deploy)
    if rc == 0:
        rc2, out2, err2 = await _sh(["git", "pull", "--ff-only", "origin", payload.branch])
        _step("git_pull", rc2 == 0, out2, err2)
        pull_ok = rc2 == 0
    else:
        pull_ok = False

    # Step 3 — supervisorctl restart backend (uvicorn --reload picks up changes
    # automatically, so restart is belt-and-suspenders; skip in production
    # where emergent deploy button is authoritative)
    restart_ok = True
    if pull_ok and deploy_env != "production":
        rc3, out3, err3 = await _sh(
            ["sudo", "supervisorctl", "restart", "backend"], timeout=30,
        )
        _step("supervisor_restart", rc3 == 0, out3, err3)
        restart_ok = rc3 == 0

    overall_ok = all(s["ok"] for s in log)
    finished_at = _now_iso()

    try:
        await _db[TRIGGERS_COLLECTION].update_one(
            {"trigger_id": trigger_id},
            {"$set": {
                "status": "success" if overall_ok else "failed",
                "finished_at": finished_at,
                "steps": log,
                "deploy_kind": deploy_env,
            }},
        )
    except Exception as e:
        logger.warning(f"[deploy_trigger] failed to update trigger doc: {e}")


@router.post("/trigger", status_code=202)
async def trigger_deploy(
    request: Request,
    payload: DeployTriggerPayload,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    """POST /api/admin/deploy/trigger — fire a deploy. 202 = accepted."""
    _verify_secret(authorization)
    _check_ip_allowlist(request)

    # Optional gating: if AUTO_HEAL_ONLY=1 then require [auto-heal] in message
    auto_heal_only = (os.environ.get("DEPLOY_AUTO_HEAL_ONLY", "0").lower()
                      in ("1", "true", "yes", "on"))
    if auto_heal_only and "[auto-heal]" not in (payload.message or ""):
        raise HTTPException(
            status_code=400,
            detail="DEPLOY_AUTO_HEAL_ONLY is set — commit message must contain [auto-heal]",
        )

    # Replay protection — dedupe on (commit, run_id)
    if _db is not None and payload.commit and payload.run_id:
        existing = await _db[TRIGGERS_COLLECTION].find_one(
            {"commit": payload.commit, "run_id": payload.run_id}, {"_id": 0, "trigger_id": 1},
        )
        if existing:
            return {
                "ok": True,
                "trigger_id": existing["trigger_id"],
                "status": "duplicate_ignored",
                "detail": "already processed this (commit, run_id)",
            }

    trigger_id = f"dep_{uuid.uuid4().hex[:12]}"
    doc = {
        "trigger_id": trigger_id,
        "trigger":  payload.trigger,
        "branch":   payload.branch,
        "commit":   payload.commit,
        "message":  payload.message,
        "actor":    payload.actor,
        "run_id":   payload.run_id,
        "ts_iso":   _now_iso(),
        "status":   "running",
        "source_ip": request.client.host if request.client else None,
        "deploy_kind": os.environ.get("AUREM_ENV", "preview").lower(),
    }

    if _db is not None:
        try:
            await _db[TRIGGERS_COLLECTION].insert_one(dict(doc))
        except Exception as e:
            logger.warning(f"[deploy_trigger] could not log trigger: {e}")

    background_tasks.add_task(_run_deploy_task, trigger_id, payload)

    return {
        "ok": True,
        "status": "Deployment Initiated",
        "trigger_id": trigger_id,
        "deploy_kind": doc["deploy_kind"],
        "poll_url": f"/api/admin/deploy/status/{trigger_id}",
    }


@router.get("/status/{trigger_id}")
async def deploy_status(
    trigger_id: str,
    authorization: Optional[str] = Header(None),
):
    """Poll the status of a prior trigger."""
    _verify_secret(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db not ready")
    doc = await _db[TRIGGERS_COLLECTION].find_one(
        {"trigger_id": trigger_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="trigger not found")
    return doc


@router.get("/health")
async def deploy_health():
    """Public liveness probe — no secret needed."""
    return {
        "ok": True,
        "component": "deploy-trigger",
        "secret_configured": bool(os.environ.get("DEPLOY_SECRET", "").strip()),
        "deploy_kind": os.environ.get("AUREM_ENV", "preview").lower(),
        "auto_heal_only": (os.environ.get("DEPLOY_AUTO_HEAL_ONLY", "0").lower()
                           in ("1", "true", "yes", "on")),
    }


@router.get("/recent")
async def deploy_recent(
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Last N triggers — audit trail."""
    _verify_secret(authorization)
    if _db is None:
        return {"triggers": []}
    out = []
    async for d in _db[TRIGGERS_COLLECTION].find({}, {"_id": 0}).sort("ts_iso", -1).limit(limit):
        out.append(d)
    return {"triggers": out, "count": len(out)}
