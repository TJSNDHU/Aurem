"""
Email Routes for Reroots
API endpoints for email automation system
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging

from services.email_ai import (
    EMAIL_TYPES,
    is_sendgrid_configured,
    generate_email_content,
    send_email,
    get_email_logs,
    get_queued_emails,
    process_queued_emails,
    set_db as set_email_db
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database
    set_email_db(database)


class SendEmailRequest(BaseModel):
    email_type: str
    to_email: EmailStr
    context: Optional[Dict[str, Any]] = None
    test_mode: bool = False


class PreviewEmailRequest(BaseModel):
    email_type: str
    customer_email: Optional[EmailStr] = "test@example.com"
    context: Optional[Dict[str, Any]] = None


async def get_current_user(request: Request):
    """Get current user from request (simplified)"""
    from server import get_current_user as server_get_user
    return await server_get_user(request)


@router.get("/types")
async def get_email_types():
    """Get all available email types"""
    return {
        "success": True,
        "types": EMAIL_TYPES,
        "sendgrid_configured": is_sendgrid_configured()
    }


@router.get("/status")
async def get_email_status(request: Request):
    """Get email system status"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    queued = await get_queued_emails()
    recent_logs = await get_email_logs(limit=10)
    
    # Count by status
    sent_count = sum(1 for log in recent_logs if log.get("status") == "sent")
    queued_count = len(queued)
    
    return {
        "success": True,
        "sendgrid_configured": is_sendgrid_configured(),
        "stats": {
            "total_queued": queued_count,
            "recent_sent": sent_count,
            "recent_total": len(recent_logs)
        },
        "types": list(EMAIL_TYPES.keys())
    }


@router.post("/send")
async def send_email_endpoint(request: Request, body: SendEmailRequest):
    """Send email via SendGrid or queue if not configured"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if body.email_type not in EMAIL_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid email type: {body.email_type}")
    
    # Generate content
    content = await generate_email_content(
        body.email_type,
        body.to_email,
        body.context
    )
    
    if not content.get("success"):
        raise HTTPException(status_code=500, detail=content.get("error", "Failed to generate email"))
    
    # Send or queue
    result = await send_email(
        to_email=body.to_email,
        subject=content["subject"],
        html_content=content["body"],
        email_type=body.email_type,
        test_mode=body.test_mode
    )
    
    return {
        "success": result.get("success", False),
        "status": result.get("status"),
        "message": result.get("message"),
        "sendgrid_configured": is_sendgrid_configured(),
        "email": {
            "to": body.to_email,
            "subject": content["subject"],
            "type": body.email_type
        }
    }


@router.get("/logs")
async def get_email_logs_endpoint(
    request: Request,
    limit: int = 50,
    email_type: Optional[str] = None
):
    """Get email logs (admin only)"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logs = await get_email_logs(limit=limit, email_type=email_type)
    
    return {
        "success": True,
        "logs": logs,
        "count": len(logs),
        "sendgrid_configured": is_sendgrid_configured()
    }


@router.get("/preview/{email_type}")
async def preview_email(request: Request, email_type: str, customer_email: str = "demo@reroots.ca"):
    """Preview email template with sample content"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if email_type not in EMAIL_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid email type: {email_type}")
    
    # Generate preview content
    content = await generate_email_content(email_type, customer_email)
    
    if not content.get("success"):
        raise HTTPException(status_code=500, detail=content.get("error", "Failed to generate preview"))
    
    return {
        "success": True,
        "email_type": email_type,
        "config": EMAIL_TYPES[email_type],
        "subject": content["subject"],
        "body": content["body"],
        "personalization": content.get("personalization", {})
    }


@router.post("/preview")
async def preview_email_post(request: Request, body: PreviewEmailRequest):
    """Preview email with custom context"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if body.email_type not in EMAIL_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid email type: {body.email_type}")
    
    content = await generate_email_content(
        body.email_type,
        body.customer_email,
        body.context
    )
    
    if not content.get("success"):
        raise HTTPException(status_code=500, detail=content.get("error", "Failed to generate preview"))
    
    return {
        "success": True,
        "email_type": body.email_type,
        "config": EMAIL_TYPES[body.email_type],
        "subject": content["subject"],
        "body": content["body"],
        "personalization": content.get("personalization", {})
    }


@router.post("/process-queue")
async def process_queue(request: Request):
    """Process all queued emails (when SendGrid is configured)"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not is_sendgrid_configured():
        return {
            "success": False,
            "message": "SendGrid not configured. Add SENDGRID_API_KEY to process queue.",
            "queued_count": len(await get_queued_emails())
        }
    
    result = await process_queued_emails()
    
    return {
        "success": True,
        "processed": result.get("sent", 0),
        "failed": result.get("failed", 0),
        "total": result.get("total", 0)
    }


@router.get("/queued")
async def get_queued(request: Request):
    """Get count of queued emails"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    queued = await get_queued_emails()
    
    return {
        "success": True,
        "count": len(queued),
        "sendgrid_configured": is_sendgrid_configured(),
        "emails": [
            {
                "to": e.get("to_email"),
                "type": e.get("email_type"),
                "created_at": e.get("created_at")
            }
            for e in queued[:20]
        ]
    }
