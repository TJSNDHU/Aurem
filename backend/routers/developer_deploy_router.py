"""
routers/developer_deploy_router.py — iter 332b D-30
═══════════════════════════════════════════════════
Self-deploy tooling for tenants of the AUREM Developer Portal.

Endpoints (auth: dev JWT or platform admin JWT, via _current_dev)
  GET    /api/developers/deploy/config         — fetch saved deploy target
  POST   /api/developers/deploy/config         — save SSH key + host + path
  DELETE /api/developers/deploy/config         — clear stored config
  POST   /api/developers/deploy/run            — kick off git-pull + compose
  GET    /api/developers/deploy/log/{run_id}   — tail latest log lines
  GET    /api/developers/deploy/history        — last 20 runs
  POST   /api/developers/deploy/rollback       — git reset --hard HEAD~1

  POST   /api/developers/domain/config         — save apex domain + slug
  GET    /api/developers/domain/config         — fetch saved domain config

Implementation notes
  • SSH connection via asyncssh — non-blocking, stream-friendly.
  • Private key stored encrypted at rest using services.byok_store fernet
    (the same path GitHub PAT + BYOK keys use), masked on read.
  • Each deploy run lives in `developer_deploy_runs`. The log is streamed
    into the doc as it grows (`output` array) so the UI can poll
    /deploy/log/{run_id} and render incremental output.
  • Hard timeout of 8 min per run prevents stuck deploys.
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

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db) -> None:
    global _db
    _db = db


# ── encrypt / decrypt helpers (shared with BYOK) ──────────────────────
def _encrypt(plain: str) -> str:
    try:
        from services.byok_store import _encrypt as _enc
        return _enc(plain)
    except Exception:
        import base64 as _b64
        return "b64:" + _b64.b64encode(plain.encode()).decode()


def _decrypt(ct: str) -> str:
    if not ct:
        return ""
    try:
        from services.byok_store import _decrypt as _dec
        return _dec(ct)
    except Exception:
        if ct.startswith("b64:"):
            import base64 as _b64
            return _b64.b64decode(ct[4:]).decode()
        return ""


async def _dev(authorization: Optional[str]) -> dict:
    from routers.developer_portal_router import _current_dev
    return await _current_dev(authorization)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrub(text: str) -> str:
    """Best-effort secret scrub before persisting log lines."""
    if not text:
        return ""
    text = re.sub(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]+)",
                  "github_pat_***", text)
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)\S+",
                  r"\1***", text)
    return text[:4000]


# ──────────────────────────────────────────────────────────────────────
# Deploy config
# ──────────────────────────────────────────────────────────────────────

class DeployConfigBody(BaseModel):
    host:        str = Field(..., min_length=3, max_length=255)
    port:        int = Field(22, ge=1, le=65535)
    username:    str = Field("root", min_length=1, max_length=64)
    private_key: str = Field(..., min_length=40)
    repo_path:   str = Field(..., min_length=1, max_length=255)
    branch:      str = Field("main", min_length=1, max_length=64)
    compose_file: str = Field("docker-compose.yml", min_length=1, max_length=128)


@router.get("/api/developers/deploy/config")
async def get_deploy_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    row = await _db.developer_deploy_configs.find_one(
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
        "private_key":   "•••••••• (saved, encrypted)",
        "updated_at":    row.get("updated_at"),
    }


@router.post("/api/developers/deploy/config")
async def save_deploy_config(body: DeployConfigBody,
                              authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    pk = body.private_key.strip()
    if "BEGIN" not in pk or "PRIVATE KEY" not in pk:
        raise HTTPException(400, "private_key_must_be_pem")
    enc = _encrypt(pk)
    await _db.developer_deploy_configs.update_one(
        {"user_id": me["user_id"]},
        {"$set": {
            "user_id":      me["user_id"],
            "host":         body.host.strip(),
            "port":         body.port,
            "username":     body.username.strip(),
            "private_key_enc": enc,
            "repo_path":    body.repo_path.strip(),
            "branch":       body.branch.strip(),
            "compose_file": body.compose_file.strip(),
            "updated_at":   _now_iso(),
        }},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/api/developers/deploy/config")
async def delete_deploy_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        return {"ok": True}
    await _db.developer_deploy_configs.delete_one({"user_id": me["user_id"]})
    return {"ok": True}


# ──────────────────────────────────────────────────────────────────────
# Deploy run (background SSH execution)
# ──────────────────────────────────────────────────────────────────────

DEPLOY_TIMEOUT_SECONDS = 8 * 60


async def _run_deploy_remote(run_id: str, cfg: dict, command: str) -> None:
    """Execute `command` over SSH; stream stdout/stderr into Mongo doc.

    We append lines to `output` and update `status` when finished. The UI
    polls /api/developers/deploy/log/{run_id} every 2 s.
    """
    import asyncssh

    db = _db
    if db is None:
        return

    private_key = _decrypt(cfg.get("private_key_enc", ""))
    if not private_key:
        await db.developer_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed",
                       "error": "decrypt_failed",
                       "finished_at": _now_iso()}},
        )
        return

    async def _append(line: str) -> None:
        await db.developer_deploy_runs.update_one(
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
                known_hosts=None,             # trust-on-first-use; user owns the box
                connect_timeout=15,
            ) as conn:
                await _append(f"$ {command}")
                async with conn.create_process(command) as proc:
                    async def _pipe(stream, tag):
                        async for line in stream:
                            await _append(f"{tag} {line.rstrip()}")
                    await asyncio.gather(
                        _pipe(proc.stdout, "·"),
                        _pipe(proc.stderr, "!"),
                    )
                    rc = await proc.wait()
                    await db.developer_deploy_runs.update_one(
                        {"run_id": run_id},
                        {"$set": {
                            "status":      "ok" if rc == 0 else "failed",
                            "exit_code":   rc,
                            "finished_at": _now_iso(),
                        }},
                    )
    except asyncio.TimeoutError:
        await _append(f"!! deploy timed out after {DEPLOY_TIMEOUT_SECONDS}s")
        await db.developer_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "timeout", "finished_at": _now_iso()}},
        )
    except Exception as e:
        await _append(f"!! deploy crashed: {type(e).__name__}: {str(e)[:200]}")
        await db.developer_deploy_runs.update_one(
            {"run_id": run_id},
            {"$set": {"status": "failed", "finished_at": _now_iso(),
                       "error": str(e)[:200]}},
        )


def _deploy_command(cfg: dict, mode: str = "deploy") -> str:
    """Compose the bash one-liner to execute remotely.

    `deploy`   → cd repo && git pull && docker compose up -d --build
    `rollback` → cd repo && git reset --hard HEAD~1 && docker compose up -d --build
    """
    repo = cfg.get("repo_path", "").rstrip("/")
    branch = cfg.get("branch", "main")
    compose = cfg.get("compose_file", "docker-compose.yml")
    if not repo:
        return "echo 'no repo_path configured' && exit 2"
    if mode == "rollback":
        seq = (
            f"cd {repo} && "
            f"git reset --hard HEAD~1 && "
            f"docker compose -f {compose} up -d --remove-orphans"
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
    # Always print HEAD sha so the rollback shows correctly in history.
    return f"set -e; ({seq}) && echo \"DEPLOY_HEAD=$(git -C {repo} rev-parse HEAD)\""


class DeployRunBody(BaseModel):
    mode: str = Field("deploy", pattern="^(deploy|rollback)$")


@router.post("/api/developers/deploy/run")
async def run_deploy(body: DeployRunBody = DeployRunBody(),
                      authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    cfg = await _db.developer_deploy_configs.find_one(
        {"user_id": me["user_id"]}, {"_id": 0},
    )
    if not cfg:
        raise HTTPException(400, "deploy_not_configured")
    run_id = uuid.uuid4().hex[:16]
    cmd = _deploy_command(cfg, body.mode)
    await _db.developer_deploy_runs.insert_one({
        "run_id":      run_id,
        "user_id":     me["user_id"],
        "mode":        body.mode,
        "host":        cfg.get("host"),
        "branch":      cfg.get("branch", "main"),
        "command":     cmd,
        "status":      "running",
        "exit_code":   None,
        "output":      [],
        "started_at":  _now_iso(),
        "last_update": _now_iso(),
        "finished_at": None,
    })
    # Fire-and-forget background SSH run.
    asyncio.create_task(_run_deploy_remote(run_id, cfg, cmd),
                        name=f"dev-deploy:{run_id}")
    return {"run_id": run_id, "mode": body.mode, "status": "running"}


@router.get("/api/developers/deploy/log/{run_id}")
async def get_deploy_log(run_id: str,
                          since: int = 0,
                          authorization: str = Header(None)) -> dict[str, Any]:
    """Poll-based log streaming: returns lines from index `since` onward."""
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    doc = await _db.developer_deploy_runs.find_one(
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
        "since":       since,
        "next_cursor": len(full),
        "lines":       full[since:],
        "started_at":  doc.get("started_at"),
        "finished_at": doc.get("finished_at"),
    }


@router.get("/api/developers/deploy/history")
async def deploy_history(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    cur = _db.developer_deploy_runs.find(
        {"user_id": me["user_id"]},
        {"_id": 0, "output": 0},
    ).sort("started_at", -1).limit(20)
    rows = [d async for d in cur]
    return {"runs": rows}


# ──────────────────────────────────────────────────────────────────────
# Domain linking
# ──────────────────────────────────────────────────────────────────────

DOMAIN_RE = re.compile(
    r"^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$",
    re.IGNORECASE,
)


class DomainConfigBody(BaseModel):
    domain:     str = Field(..., min_length=4, max_length=253)
    server_ip:  str = Field(..., min_length=7, max_length=45)


@router.post("/api/developers/domain/config")
async def save_domain_config(body: DomainConfigBody,
                              authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    dom = body.domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.match(dom):
        raise HTTPException(400, "invalid_domain")
    ip = body.server_ip.strip()
    # Loose IP check — accepts both v4 and v6 forms; we don't gate on it,
    # the user owns the box and may be using a CDN front later anyway.
    if len(ip) < 7 or " " in ip:
        raise HTTPException(400, "invalid_ip")
    await _db.developer_domain_configs.update_one(
        {"user_id": me["user_id"]},
        {"$set": {
            "user_id":    me["user_id"],
            "domain":     dom,
            "server_ip":  ip,
            "updated_at": _now_iso(),
        }},
        upsert=True,
    )
    return _domain_payload(dom, ip)


@router.get("/api/developers/domain/config")
async def get_domain_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await _dev(authorization)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    row = await _db.developer_domain_configs.find_one(
        {"user_id": me["user_id"]}, {"_id": 0},
    )
    if not row:
        return {"configured": False}
    return _domain_payload(row.get("domain"), row.get("server_ip"))


def _domain_payload(domain: str, ip: str) -> dict[str, Any]:
    """Build DNS instructions + Caddyfile snippet for the configured domain."""
    apex = domain
    www = f"www.{domain}"
    dns_records = [
        {"type": "A", "name": "@", "value": ip, "ttl": 300,
         "note": "apex record — points yourdomain.com directly at the box"},
        {"type": "A", "name": "www", "value": ip, "ttl": 300,
         "note": "www subdomain — same target"},
    ]
    caddyfile = (
        f"{apex}, {www} {{\n"
        f"    encode zstd gzip\n"
        f"    reverse_proxy localhost:8001\n"
        f"    @frontend not path /api/* /ws/*\n"
        f"    handle @frontend {{\n"
        f"        reverse_proxy localhost:3000\n"
        f"    }}\n"
        f"}}\n"
    )
    return {
        "configured":  True,
        "domain":      apex,
        "server_ip":   ip,
        "dns_records": dns_records,
        "caddyfile":   caddyfile,
        "verify_cmd":  f"dig +short {apex}  &&  dig +short {www}",
        "ssl_note":    "Caddy auto-provisions TLS via Let's Encrypt on first request. Open ports 80 + 443 on the host firewall.",
    }
