"""
AUREM Database Audit Middleware — Pure ASGI Implementation
Logs API request metadata to MongoDB for compliance audit trails.
Converted from BaseHTTPMiddleware to pure ASGI to avoid Starlette ExceptionGroup crashes.
"""
import time
import logging
import asyncio
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Skip paths for performance
SKIP_PATHS = frozenset([
    "/api/health", "/health", "/ready", "/api/platform/health",
    "/api/pixel/", "/favicon.ico", "/robots.txt",
])


class DatabaseAuditMiddleware:
    """Pure ASGI middleware for database audit logging."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip non-auditable paths
        if path in SKIP_PATHS or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            method = scope.get("method", "GET")
            try:
                _log_audit(method, path, status_code, duration_ms)
            except Exception:
                pass

_db_ref = None


def set_db(database):
    """Set DB reference to avoid circular import with server.py."""
    global _db_ref
    _db_ref = database
    # iter 322db — TTL index on api_audit_log so the collection auto-purges
    # rows older than 35 days. Prevents unbounded growth. 35 d is just over
    # the classifier's 30-d window so the signal stays valid.
    if database is not None:
        try:
            import asyncio
            async def _ensure_ttl():
                try:
                    await database.api_audit_log.create_index(
                        "ts", expireAfterSeconds=35 * 24 * 3600, name="ts_ttl_35d",
                    )
                except Exception:
                    pass
            asyncio.create_task(_ensure_ttl())
        except Exception:
            pass

    
def _log_audit(method: str, path: str, status_code: int, duration_ms: float):
    """Fire-and-forget audit log (non-blocking)."""
    try:
        db = _db_ref
        if db is None:
            try:
                import server
                db = getattr(server, "db", None)
            except Exception:
                pass
        if db is not None:
            asyncio.get_event_loop().create_task(
                _async_log_audit(db, method, path, status_code, duration_ms)
            )
    except Exception:
        pass


async def _async_log_audit(db, method, path, status_code, duration_ms):
    """Write audit entry to MongoDB."""
    try:
        import datetime
        await db.api_audit_log.insert_one({
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp": datetime.datetime.now(datetime.timezone.utc),
            "action": _method_to_action(method),
        })
    except Exception:
        pass


def _method_to_action(method: str) -> str:
    return {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method, "unknown")
