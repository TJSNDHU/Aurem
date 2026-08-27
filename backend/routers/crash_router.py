from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()

ALLOWED_SERVICES = {
    "auth-service",
    "payment-service",
    "notification-service",
    "user-service",
    "order-service",
    "inventory-service",
    "analytics-service",
    "gateway-service",
}


class CrashReport(BaseModel):
    service: str
    error_message: str | None = None
    stack_trace: str | None = None
    severity: str | None = "error"


@router.post("/crash")
async def handle_crash(report: CrashReport, request: Request):
    service = report.service

    if service not in ALLOWED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown service '{service}'. Allowed services: {sorted(ALLOWED_SERVICES)}",
        )

    # Process the crash report for a known service
    # (DB write, logging, alerting, etc. would go here)
    return {
        "status": "received",
        "service": service,
        "message": "Crash report recorded successfully.",
    }