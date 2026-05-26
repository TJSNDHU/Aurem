"""
aurem_cto.routers.vault — P7 audit-log surface.

The encryption itself lives in services/crypto.py. This router only
exposes a read-only audit-log endpoint so the customer (and AUREM
admin) can see every encrypt/decrypt event against their account.
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(prefix="/vault", tags=["AUREM CTO Vault"])


@router.get("/audit-log")
async def audit_log(limit: int = 100,
                     authorization: str = Header(None)) -> dict:
    me = await current_dev(authorization)
    db = require_db()
    limit = max(1, min(int(limit), 500))
    cur = db.aurem_cto_vault_audit_log.find(
        {"user_id": me["user_id"]},
        {"_id": 0},
    ).sort("ts", -1).limit(limit)
    rows = [d async for d in cur]
    # ts comes back as ISO string for JSON safety
    for r in rows:
        ts = r.get("ts")
        if hasattr(ts, "isoformat"):
            r["ts"] = ts.isoformat()
    return {"events": rows, "count": len(rows)}
