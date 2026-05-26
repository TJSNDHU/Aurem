"""
aurem_cto.routers.deploy — P0 foundation.

SSH-driven `git pull && docker compose up -d` with live log streaming,
last-N run history, and one-click rollback.

Routes mount under /aurem-cto/deploy/* via the parent build_router().
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..services.auth import current_dev
from ..services.crypto import encrypt, decrypt, is_vault_available
from ..services.db import require_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deploy", tags=["AUREM CTO Deploy"])

DEPLOY_TIMEOUT_SECONDS = 8 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrub(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]+)",
                  "github_pat_***", text)
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)\S+", r"\1***", text)
    return text[:4000]


class DeployConfigBody(BaseModel):
    host:         str = Field(..., min_length=3, max_length=255)
    port:         int = Field(22, ge=1, le=65535)
    username:     str = Field("root", min_length=1, max_length=64)
    private_key:  str = Field(..., min_length=40)
    repo_path:    str = Field(..., min_length=1, max_length=255)
    branch:       str = Field("main", min_length=1, max_length=64)
    compose_file: str = Field("docker-compose.yml", min_length=1, max_length=128)


@router.get("/config")
async def get_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_deploy_configs.find_one(
        {"user_id": me["user_id"]}, {"_id": 0},
    )
    if not row:
        return {"configured": False}
    return {
        "configured":    True,
        "host":          row.get("host"),
        "port":          row.get("port", 22),
        "username":      row.get("username", "root"),
        "repo_path":     row.get("repo_path"),
        "branch":        row.get("branch", "main"),
        "compose_file":  row.get("compose_file", "docker-compose.yml"),
        "private_key":   "•••••••• (write-only — never returned)",
        "updated_at":    row.get("updated_at"),
    }


@router.post("/config")
async def save_config(body: DeployConfigBody,
                      authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    if not is_vault_available():
        raise HTTPException(503, {
            "code": "vault_unavailable",
            "msg":  "AUREM_CTO_MASTER_KEY not set on this deployment — "
                    "ask an admin to configure the vault env var.",
        })
    pk = body.private_key.strip()
    if "BEGIN" not in pk or "PRIVATE KEY" not in pk:
        raise HTTPException(400, "private_key_must_be_pem")
    enc = await encrypt(me["user_id"], pk, kind="ssh_private_key")
    await db.aurem_cto_deploy_configs.update_one(
        {"user_id": me["user_id"]},
        {"$set": {
            "user_id":         me["user_id"],
            "host":            body.host.strip(),
            "port":            body.port,
            "username":        body.username.strip(),
            "private_key_enc": enc,
            "repo_path":       body.repo_path.strip(),
            "branch":          body.branch.strip(),
            "compose_file":    body.compose_file.strip(),
            "updated_at":      _now_iso(),
        }},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/config")
async def delete_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    await db.aurem_cto_deploy_configs.delete_one({"user_id": me["user_id"]})
    return {"ok": True}


def _deploy_command(cfg: dict, mode: str = "deploy") -> str:
    repo = cfg.get("repo_path", "").rstrip("/")
    branch = cfg.get("branch", "main")
    compose = cfg.get("compose_file", "docker-compose.yml")
    if not repo:
        return "echo 'no repo_path configured' && exit 2"
    if mode == "dry_run":
        # D-35 — safe staging check. Verifies SSH auth, repo access and
        # docker-compose validity WITHOUT pulling code or restarting
        # containers. Used to gate the real-deploy button on production
        # dogfood projects.
        seq = (
            f"cd {repo} && "
            f"git fetch --all --prune && "
            f"docker compose -f {compose} config --quiet && "
            f"echo DRY_RUN_OK"
        )
    elif mode == "rollback":
        seq = (
            f"cd {repo} && "
            f"git reset --hard HEAD~1 && "
            f"docker compose -f {compose} up -d --remove-orphans"
        )
    elif mode == "revert_to":
        sha = cfg.get("_revert_sha", "").strip()
        if not re.fullmatch(r"[0-9a-f]{7,64}", sha):
            return "echo 'bad sha' && exit 2"
        seq = (
            f"cd {repo} && "
            f"git fetch --all --prune && "
            f"git revert --no-edit {sha} && "
            f"git push origin {branch} && "
            f"docker compose -f {compose} up -d --build --remove-orphans"
        )
    else:
        seq = (
            f"cd {repo} && "
            f"git fetch --all --prune && "
            f"git checkout {branch} && "
            f"git pull --ff-only origin {branch} && "
            f"docker compose -f {compose} pull && "
            f"docker compose -f {compose} up -d --remove-orphans --build"
        )
    return (
        f"set -e; ({seq}) && "
        f"echo \"DEPLOY_HEAD=$(git -C {repo} rev-parse HEAD)\""
    )


async def _run_deploy_remote(user_id: str, run_id: str,
                              cfg: dict, command: str) -> None:
    import asyncssh
    db = require_db()

    try:
        private_key = await decrypt(user_id, cfg.get("private_key_enc", ""),
                                     kind="ssh_private_key")
    except Exception as e:
        await db.aurem_cto_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed",
                       "error": f"vault_decrypt_failed: {type(e).__name__}",
                       "finished_at": _now_iso()}},
        )
        return

    async def _append(line: str) -> None:
        await db.aurem_cto_deploy_runs.update_one(
            {"run_id": run_id},
            {"$push": {"output": _scrub(line)},
             "$set":  {"last_update": _now_iso()}},
        )

    try:
        async with asyncio.timeout(DEPLOY_TIMEOUT_SECONDS):
            async with asyncssh.connect(
                cfg["host"], port=int(cfg.get("port", 22)),
                username=cfg.get("username", "root"),
                client_keys=[asyncssh.import_private_key(private_key)],
                known_hosts=None,
                connect_timeout=15,
            ) as conn:
                await _append(f"$ {command}")
                async with conn.create_process(command) as proc:
                    head_sha: Optional[str] = None

                    async def _pipe(stream, tag):
                        nonlocal head_sha
                        async for line in stream:
                            stripped = line.rstrip()
                            if stripped.startswith("DEPLOY_HEAD="):
                                head_sha = stripped.split("=", 1)[1].strip()
                            await _append(f"{tag} {stripped}")
                    await asyncio.gather(
                        _pipe(proc.stdout, "·"),
                        _pipe(proc.stderr, "!"),
                    )
                    rc = await proc.wait()
                    await db.aurem_cto_deploy_runs.update_one(
                        {"run_id": run_id},
                        {"$set": {
                            "status":      "ok" if rc == 0 else "failed",
                            "exit_code":   rc,
                            "head_sha":    head_sha,
                            "finished_at": _now_iso(),
                        }},
                    )
    except asyncio.TimeoutError:
        await _append(f"!! deploy timed out after {DEPLOY_TIMEOUT_SECONDS}s")
        await db.aurem_cto_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "timeout", "finished_at": _now_iso()}},
        )
    except Exception as e:
        await _append(f"!! deploy crashed: {type(e).__name__}: {str(e)[:200]}")
        await db.aurem_cto_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "finished_at": _now_iso(),
                       "error": f"{type(e).__name__}: {str(e)[:200]}"}},
        )


class DeployRunBody(BaseModel):
    mode:      str = Field("deploy",
                            pattern="^(deploy|rollback|revert_to|dry_run)$")
    sha:       str = Field("", max_length=64)   # only used when mode=revert_to
    message_id: str = Field("", max_length=64)  # optional chat-message link
    project_id: str = Field("", max_length=64)  # optional dogfood project link


@router.post("/run")
async def run_deploy(body: DeployRunBody = DeployRunBody(),
                     authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    cfg = await db.aurem_cto_deploy_configs.find_one(
        {"user_id": me["user_id"]}, {"_id": 0},
    )
    if not cfg:
        raise HTTPException(400, "deploy_not_configured")

    # D-35 — Production dogfood guard.
    # If the caller links this run to a project flagged
    # is_production_dogfood, the REAL deploy (mode in deploy/revert_to)
    # is blocked until a dry-run for the SAME user has completed with
    # status=ok in the last 24h. Rollback is always allowed (it's the
    # emergency exit).
    if body.project_id and body.mode in ("deploy", "revert_to"):
        proj = await db.onboarding_projects.find_one(
            {"project_id": body.project_id, "user_id": me["user_id"]},
            {"_id": 0, "is_production_dogfood": 1},
        )
        if proj and proj.get("is_production_dogfood"):
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            ok_dry = await db.aurem_cto_deploy_runs.find_one(
                {"user_id":   me["user_id"],
                 "mode":      "dry_run",
                 "status":    "ok",
                 "started_at": {"$gte": cutoff}},
                {"_id": 0, "run_id": 1},
            )
            if not ok_dry:
                raise HTTPException(409, {
                    "code": "dry_run_required",
                    "msg":  "Production dogfood requires a successful "
                            "dry-run within the last 24h before a real "
                            "deploy.",
                })

    if body.mode == "revert_to":
        cfg = {**cfg, "_revert_sha": body.sha}
    run_id = uuid.uuid4().hex[:16]
    cmd = _deploy_command(cfg, body.mode)
    await db.aurem_cto_deploy_runs.insert_one({
        "run_id":      run_id,
        "user_id":     me["user_id"],
        "mode":        body.mode,
        "host":        cfg.get("host"),
        "branch":      cfg.get("branch", "main"),
        "message_id":  body.message_id or None,
        "project_id":  body.project_id or None,
        "command":     cmd,
        "status":      "running",
        "exit_code":   None,
        "output":      [],
        "started_at":  _now_iso(),
        "last_update": _now_iso(),
        "finished_at": None,
    })
    asyncio.create_task(_run_deploy_remote(me["user_id"], run_id, cfg, cmd),
                        name=f"aurem-cto-deploy:{run_id}")
    return {"run_id": run_id, "mode": body.mode, "status": "running"}


@router.get("/log/{run_id}")
async def get_log(run_id: str,
                  since: int = 0,
                  authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    doc = await db.aurem_cto_deploy_runs.find_one(
        {"run_id": run_id, "user_id": me["user_id"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "run_not_found")
    full = doc.get("output", []) or []
    return {
        "run_id":      run_id,
        "status":      doc.get("status"),
        "exit_code":   doc.get("exit_code"),
        "head_sha":    doc.get("head_sha"),
        "since":       since,
        "next_cursor": len(full),
        "lines":       full[since:],
        "started_at":  doc.get("started_at"),
        "finished_at": doc.get("finished_at"),
    }


@router.get("/history")
async def history(authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    cur = db.aurem_cto_deploy_runs.find(
        {"user_id": me["user_id"]},
        {"_id": 0, "output": 0},
    ).sort("started_at", -1).limit(20)
    rows = [d async for d in cur]
    return {"runs": rows}
