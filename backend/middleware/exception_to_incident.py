"""
exception_to_incident.py — FastAPI middleware that auto-captures every
5xx response into the incident bus (iter 322ff).

We do NOT interfere with the response — we observe, log, and continue.
The incident bus has its own dedup, so a 502 storm = 1 incident, not 1000.

Wire-up:
    from middleware.exception_to_incident import ExceptionToIncidentMiddleware
    app.add_middleware(ExceptionToIncidentMiddleware)
"""
from __future__ import annotations

import logging
import traceback
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Routes we don't want to spam-report (already metrics or noisy by design)
_SKIP_PREFIXES = (
    "/api/platform/health",
    "/api/incident/",      # don't loop the bus into itself
    "/health",
    "/ready",
    "/metrics",
)


class ExceptionToIncidentMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            await self._report_exception(request, exc)
            raise
        else:
            try:
                if response.status_code >= 500 and not self._skip(request.url.path):
                    await self._report_5xx(request, response.status_code)
            except Exception as e:
                logger.debug(f"[exc-to-incident] post-response report failed: {e}")
            return response

    @staticmethod
    def _skip(path: str) -> bool:
        return any(path.startswith(p) for p in _SKIP_PREFIXES)

    async def _report_exception(self, request: Request, exc: BaseException) -> None:
        if self._skip(request.url.path):
            return
        try:
            from services import incident_bus
            sig = f"{type(exc).__name__}:{request.method} {request.url.path}"
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-2000:]
            await incident_bus.report(
                category="backend_5xx",
                signature=sig[:240],
                severity="P1",
                source="backend_middleware",
                title=f"Unhandled {type(exc).__name__} on {request.url.path}",
                detail=tb,
                metadata={
                    "path":   request.url.path,
                    "method": request.method,
                    "qs":     str(request.url.query)[:240],
                },
                actor="exception_to_incident",
            )
        except Exception as e:
            logger.debug(f"[exc-to-incident] exception ingest failed: {e}")

    async def _report_5xx(self, request: Request, status: int) -> None:
        try:
            from services import incident_bus
            sig = f"HTTP {status}:{request.method} {request.url.path}"
            cat = "transient_502" if status in (502, 503, 504) else "backend_5xx"
            sev = "P1" if status in (500, 503, 504) else "P2"
            await incident_bus.report(
                category=cat,
                signature=sig[:240],
                severity=sev,
                source="backend_middleware",
                title=f"HTTP {status} on {request.url.path}",
                detail=f"Status: {status}\nPath: {request.url.path}\nMethod: {request.method}",
                metadata={
                    "path":   request.url.path,
                    "method": request.method,
                    "status": status,
                },
                actor="exception_to_incident",
            )
        except Exception as e:
            logger.debug(f"[exc-to-incident] 5xx ingest failed: {e}")
