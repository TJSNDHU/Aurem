"""
aurem_cto.routers.domain — P4 placeholder.

Domain linking + 60-s cron verification probe. Builds the DNS-record
table and Caddyfile snippet; once P4 lands, adds the verification
badge + LE staging gate.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(prefix="/domain", tags=["AUREM CTO Domain"])

DOMAIN_RE = re.compile(
    r"^([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainConfigBody(BaseModel):
    domain:    str = Field(..., min_length=4, max_length=253)
    server_ip: str = Field(..., min_length=7, max_length=45)


def _payload(domain: str, ip: str, verification: dict | None = None) -> dict:
    apex = domain
    www = f"www.{domain}"
    dns_records = [
        {"type": "A", "name": "@",   "value": ip, "ttl": 300,
         "note": "apex record"},
        {"type": "A", "name": "www", "value": ip, "ttl": 300,
         "note": "www subdomain"},
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
        "ssl_note":    "Caddy auto-issues TLS via Let's Encrypt on first request.",
        "verification": verification or {
            "status": "pending",
            "last_check": None,
            "apex_ip":  None,
            "www_ip":   None,
        },
    }


@router.get("/config")
async def get_config(authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_domain_configs.find_one(
        {"user_id": me["user_id"]}, {"_id": 0},
    )
    if not row:
        return {"configured": False}
    return _payload(row.get("domain"), row.get("server_ip"),
                    verification=row.get("verification"))


@router.post("/config")
async def save_config(body: DomainConfigBody,
                      authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    dom = body.domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.match(dom):
        raise HTTPException(400, "invalid_domain")
    ip = body.server_ip.strip()
    if len(ip) < 7 or " " in ip:
        raise HTTPException(400, "invalid_ip")
    await db.aurem_cto_domain_configs.update_one(
        {"user_id": me["user_id"]},
        {"$set": {
            "user_id":    me["user_id"],
            "domain":     dom,
            "server_ip":  ip,
            "updated_at": _now_iso(),
            "verification": {
                "status": "pending", "last_check": None,
                "apex_ip": None, "www_ip": None,
            },
        }},
        upsert=True,
    )
    return _payload(dom, ip)


@router.get("/verification/{domain}")
async def verification_status(domain: str,
                               authorization: str = Header(None)) -> dict[str, Any]:
    """Returns the latest 60-s probe result for the given domain."""
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_domain_configs.find_one(
        {"user_id": me["user_id"], "domain": domain.lower()},
        {"_id": 0, "verification": 1, "server_ip": 1},
    )
    if not row:
        raise HTTPException(404, "domain_not_configured")
    return {
        "domain":       domain.lower(),
        "server_ip":    row.get("server_ip"),
        "verification": row.get("verification") or {"status": "pending"},
    }
