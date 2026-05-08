"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Honeypot Endpoints — Decoy routes that no legitimate client would call.
Any access is flagged as suspicious reconnaissance.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Honeypot"])

db = None

def set_db(database):
    global db
    db = database

HONEYPOT_PATHS = [
    "/api/internal/debug-console",
    "/api/admin/export-all-data",
    "/api/system/dump-schema",
]


async def _flag_suspicious(request: Request, path: str):
    """Log and flag suspicious IP that hit a honeypot."""
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    auth = request.headers.get("authorization", "none")

    entry = {
        "ip": ip,
        "user_agent": user_agent,
        "path": path,
        "method": request.method,
        "has_auth": auth != "none",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "threat_type": "honeypot_trigger",
        "severity": "high",
    }

    logger.warning(f"[HONEYPOT] Suspicious access from {ip} -> {path}")

    if db is not None:
        try:
            await db.suspicious_ips.update_one(
                {"ip": ip},
                {
                    "$set": {"last_seen": entry["timestamp"], "user_agent": user_agent},
                    "$inc": {"hit_count": 1},
                    "$push": {"events": {"$each": [entry], "$slice": -50}},
                    "$setOnInsert": {"first_seen": entry["timestamp"]},
                },
                upsert=True,
            )
            await db.security_events.insert_one(entry)
        except Exception as e:
            logger.error(f"[HONEYPOT] DB write failed: {e}")


@router.get("/api/internal/debug-console")
@router.post("/api/internal/debug-console")
async def honeypot_debug(request: Request):
    await _flag_suspicious(request, "/api/internal/debug-console")
    return JSONResponse(status_code=403, content={"error": "Forbidden"})


@router.get("/api/admin/export-all-data")
@router.post("/api/admin/export-all-data")
async def honeypot_export(request: Request):
    await _flag_suspicious(request, "/api/admin/export-all-data")
    return JSONResponse(status_code=403, content={"error": "Forbidden"})


@router.get("/api/system/dump-schema")
@router.post("/api/system/dump-schema")
async def honeypot_schema(request: Request):
    await _flag_suspicious(request, "/api/system/dump-schema")
    return JSONResponse(status_code=403, content={"error": "Forbidden"})


@router.get("/api/security/suspicious-ips")
async def get_suspicious_ips(request: Request):
    """Admin-only: view flagged IPs."""
    if db is None:
        return {"ips": [], "count": 0}
    ips = await db.suspicious_ips.find(
        {}, {"_id": 0}
    ).sort("hit_count", -1).to_list(100)
    return {"ips": ips, "count": len(ips)}
