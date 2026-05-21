"""
Error Ledger — Phase 4 (Code Layer)
=====================================
Central registry for every uncaught backend exception. Consumed by
auto_repair.py, agent_health_check, and the ORA Brain.

Schema (`error_ledger` collection):
  _id          ObjectId
  error_hash   sha1(message + path + traceback_top_frame)   — dedupe key
  error_type   exception class name
  message      str (first 500 chars)
  path         request path (or "background")
  traceback    str (first 4000 chars)
  count        int — incremented on duplicate hashes
  first_seen   datetime
  last_seen    datetime
  status       open | repairing | resolved
  fix_pattern  str (when auto-repair patches it)
  fix_ts       datetime

Public:
  - record_error(exc, *, path=None, extra=None)
  - install_crash_catcher(app)   — FastAPI middleware
  - install_global_exception_hook()
  - mark_resolved(error_hash, *, fix_pattern=None)
  - top_open(limit)              — for digest + ORA Brain
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import traceback as _tb
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

LEDGER = "error_ledger"
SAMPLE_SAVE = "error_samples"


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _hash(error_type: str, message: str, top_frame: str) -> str:
    raw = f"{error_type}|{message[:120]}|{top_frame[:120]}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _top_frame(tb_str: str) -> str:
    """Last meaningful frame from traceback (used in dedupe hash)."""
    lines = [ln for ln in tb_str.splitlines() if 'File "' in ln]
    return lines[-1].strip() if lines else ""


async def record_error(
    exc: BaseException,
    *,
    path: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Persist an exception. Returns the error_hash."""
    db = _get_db()
    if db is None:
        return None
    err_type = type(exc).__name__
    msg = (str(exc) or "")[:500]
    tb_str = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))[:4000]
    h = _hash(err_type, msg, _top_frame(tb_str))
    now = _utc()
    try:
        await db[LEDGER].update_one(
            {"error_hash": h},
            {
                "$setOnInsert": {
                    "error_hash": h,
                    "error_type": err_type,
                    "message": msg,
                    "path": path or "background",
                    "traceback": tb_str,
                    "first_seen": now,
                    "status": "open",
                    "extra": extra or {},
                },
                "$set": {"last_seen": now},
                "$inc": {"count": 1},
            },
            upsert=True,
        )
        # Emit on bus so auto_repair / ora_brain can react
        try:
            from services.a2a_bus import bus
            asyncio.create_task(bus.emit(
                "error_ledger", "ERROR_CAPTURED",
                {"error_hash": h, "error_type": err_type,
                 "message": msg[:200], "path": path or "background"},
            ))
        except Exception:
            pass
        # iter 325f Phase 1.1 — emit on the canonical incident_bus too so
        # triage_brain + ora_cto_repair_agent can pick this up. Dedup happens
        # on the bus side via fingerprint.
        try:
            from services import incident_bus
            asyncio.create_task(incident_bus.report(
                category="crash",
                signature=h,
                severity="high",
                source="error_ledger",
                title=f"{err_type}: {msg[:120]}",
                detail=tb_str[:1500],
                metadata={"path": path or "background"},
                actor="error_ledger",
            ))
        except Exception:
            pass
        return h
    except Exception as e:
        logger.warning(f"[error_ledger] persist failed: {e}")
        return None


async def mark_resolved(error_hash: str, *, fix_pattern: Optional[str] = None) -> bool:
    db = _get_db()
    if db is None:
        return False
    res = await db[LEDGER].update_one(
        {"error_hash": error_hash, "status": {"$ne": "resolved"}},
        {"$set": {
            "status": "resolved",
            "fix_pattern": fix_pattern or "manual",
            "fix_ts": _utc(),
        }},
    )
    return bool(res.modified_count)


async def top_open(limit: int = 10) -> List[Dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    cursor = db[LEDGER].find(
        {"status": "open"},
        {"_id": 0, "error_hash": 1, "error_type": 1, "message": 1,
         "path": 1, "count": 1, "last_seen": 1},
    ).sort([("count", -1), ("last_seen", -1)]).limit(min(max(limit, 1), 100))
    return [d async for d in cursor]


async def stats() -> Dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"available": False}
    open_n, repairing, resolved = await asyncio.gather(
        db[LEDGER].count_documents({"status": "open"}),
        db[LEDGER].count_documents({"status": "repairing"}),
        db[LEDGER].count_documents({"status": "resolved"}),
    )
    return {
        "available": True,
        "open": open_n, "repairing": repairing, "resolved": resolved,
    }


# ─── FastAPI middleware (request-scoped crash catcher) ──────────────

def install_crash_catcher(app: FastAPI) -> None:
    """Catches every unhandled exception in the request pipeline,
    persists it to the ledger, then re-raises (or returns 500)."""

    @app.middleware("http")
    async def _crash_catcher(request: Request, call_next):
        try:
            return await call_next(request)
        except StarletteHTTPException:
            # Don't log expected 4xx
            raise
        except Exception as exc:
            try:
                await record_error(exc, path=str(request.url.path))
            except Exception:
                pass
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "type": type(exc).__name__},
            )

    logger.info("[error_ledger] crash-catcher middleware installed")


# ─── Global hook (background tasks / scheduler crashes) ──────────────

_orig_excepthook = None


def install_global_exception_hook() -> None:
    """Capture uncaught exceptions in threads and asyncio default handler."""
    global _orig_excepthook
    _orig_excepthook = sys.excepthook

    def _excepthook(exc_type, exc, tb):
        try:
            asyncio.get_event_loop().create_task(
                record_error(exc, path="threading"),
            )
        except Exception:
            pass
        if _orig_excepthook:
            _orig_excepthook(exc_type, exc, tb)

    sys.excepthook = _excepthook

    # asyncio loop exception handler
    try:
        loop = asyncio.get_event_loop()

        def _aio_handler(loop, ctx):
            exc = ctx.get("exception")
            if exc is not None:
                asyncio.create_task(record_error(exc, path="asyncio"))
            else:
                logger.warning(f"[error_ledger] aio_ctx no_exc: {ctx.get('message')}")

        loop.set_exception_handler(_aio_handler)
    except RuntimeError:
        # No running loop yet — set on startup elsewhere
        pass

    logger.info("[error_ledger] global excepthook + aio handler installed")
