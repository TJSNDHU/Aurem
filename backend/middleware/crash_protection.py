"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.
All rights reserved. Unauthorized copying, distribution,
or use of this software is strictly prohibited.
Licensed under Polaris Built Inc. commercial license.

Crash Protection — Request Timeout + Global Exception Handler
Extracted from server.py during modularization.
"""
import asyncio
import os
import logging
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

logger = logging.getLogger(__name__)

# ============= CRASH PROTECTION - TIMEOUT MIDDLEWARE =============
# Prevents runaway requests from hanging the server
from starlette.responses import JSONResponse as StarletteJSONResponse

class RequestTimeoutMiddleware:
    """
    Timeout middleware - cancels requests that take too long.
    Prevents server hang from slow operations.
    """
    
    def __init__(self, app, timeout_seconds: float = 30.0):
        self.app = app
        self.timeout = timeout_seconds
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Skip timeout for specific long-running endpoints
        no_timeout_paths = [
            "/api/ai/",       # AI calls can take longer
            "/api/voice/",    # Voice processing
            "/api/mcp/",      # MCP tools
            "/api/content/",  # Content generation
            "/api/email/",    # Email generation
            "/api/export/",   # Report exports
            "/ws/",           # WebSockets
        ]
        
        if any(path.startswith(p) for p in no_timeout_paths):
            await self.app(scope, receive, send)
            return
        
        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            # Return 504 Gateway Timeout
            response = StarletteJSONResponse(
                status_code=504,
                content={
                    "error": "Request timeout",
                    "detail": f"Request took longer than {self.timeout}s and was cancelled"
                }
            )
            await response(scope, receive, send)



# ============= CRASH PROTECTION - GLOBAL EXCEPTION HANDLER =============
# Catches all unhandled exceptions and returns friendly error messages
try:
    from services.crash_protection import log_crash, set_crash_log_db
except ImportError:
    pass


async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler - catches all unhandled exceptions.
    Register via: app.add_exception_handler(Exception, global_exception_handler)
    """
    import traceback
    import uuid
    
    logging.error(f"[CRASH_PROTECTION] Unhandled exception: {exc}", exc_info=True)
    
    try:
        asyncio.create_task(log_crash(str(request.url), exc, type(exc).__name__))
    except:
        pass

    # Sentinel Guard — fingerprint + pattern recognition (non-blocking)
    try:
        from services.sentinel_guard import record_error
        asyncio.create_task(record_error(str(request.url), exc, type(exc).__name__))
    except Exception:
        pass
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Something went wrong. Our team has been notified.",
            "request_id": str(uuid.uuid4())[:8]
        }
    )


