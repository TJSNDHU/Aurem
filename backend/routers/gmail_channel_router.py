"""
AUREM Commercial Platform - Gmail Channel Router
API endpoints for reading and sending emails

Endpoints:
- GET /api/gmail/{business_id}/messages - List emails
- GET /api/gmail/{business_id}/messages/{message_id} - Get single email
- POST /api/gmail/{business_id}/send - Send email
- GET /api/gmail/{business_id}/labels - Get labels
- POST /api/gmail/{business_id}/labels - Create label
- PUT /api/gmail/{business_id}/messages/{message_id}/read - Mark as read
- PUT /api/gmail/{business_id}/messages/{message_id}/unread - Mark as unread
- PUT /api/gmail/{business_id}/messages/{message_id}/archive - Archive message
- DELETE /api/gmail/{business_id}/messages/{message_id} - Trash message
- GET /api/gmail/{business_id}/profile - Get Gmail profile
- GET /api/gmail/{business_id}/threads/{thread_id} - Get email thread
"""

import os
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from pydantic import BaseModel, EmailStr, Field


def _require_owner_or_admin(business_id: str, request: Request):
    """Bug-fix #67 — Gmail endpoints were fully unauthenticated. Any
    HTTP caller could read every connected tenant's inbox and send mail
    from their account given just the business_id (which leaks via the
    URL). Now we require a valid JWT AND we require the caller's claim
    set to either include the same business_id OR be admin."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    import jwt as _jwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    is_admin = bool(
        payload.get("is_admin") or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
        or is_admin_email(payload.get("email"))
    )
    caller_biz = (payload.get("business_id")
                    or payload.get("bin")
                    or payload.get("tenant_id"))
    if not is_admin and caller_biz != business_id:
        raise HTTPException(403, "Business ID does not match the caller")
    return payload


router = APIRouter(prefix="/api/gmail", tags=["AUREM Gmail Channel"])

logger = logging.getLogger(__name__)

# Database reference
_db = None


def set_db(db):
    """Set database reference"""
    global _db
    _db = db


def get_db():
    """Get database reference"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    body_text: str = Field(..., min_length=1)
    body_html: Optional[str] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    reply_to_message_id: Optional[str] = None
    thread_id: Optional[str] = None


class CreateLabelRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    label_list_visibility: str = "labelShow"
    message_list_visibility: str = "show"


class MessageResponse(BaseModel):
    id: str
    thread_id: Optional[str] = None
    snippet: Optional[str] = None
    subject: str = ""
    from_email: str = Field("", alias="from")
    to: str = ""
    date: str = ""
    label_ids: List[str] = []
    body_text: Optional[str] = None
    body_html: Optional[str] = None


class SendResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[str] = None


class ProfileResponse(BaseModel):
    email_address: str
    messages_total: int = 0
    threads_total: int = 0


# ==================== ENDPOINTS ====================

@router.get("/{business_id}/messages")
async def list_messages(
    business_id: str,
    request: Request,
    query: Optional[str] = Query(None, description="Gmail search query"),
    max_results: int = Query(20, ge=1, le=100),
    page_token: Optional[str] = Query(None),
    label_ids: Optional[str] = Query(None, description="Comma-separated label IDs")
):
    """
    List emails from the connected Gmail account.
    
    Args:
        business_id: The business workspace
        query: Gmail search query (e.g., "from:customer@example.com is:unread")
        max_results: Maximum messages to return (1-100)
        page_token: Pagination token for next page
        label_ids: Filter by labels (comma-separated, e.g., "INBOX,UNREAD")
        
    Returns:
        List of messages with pagination info
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    # Parse label_ids
    labels = None
    if label_ids:
        labels = [label.strip() for label in label_ids.split(",")]
    
    result = await gmail_service.list_messages(
        business_id=business_id,
        query=query,
        max_results=max_results,
        page_token=page_token,
        label_ids=labels,
        ip_address=ip_address
    )
    
    if "error" in result and result["error"] != "Gmail not connected":
        raise HTTPException(500, result["error"])
    
    if result.get("error") == "Gmail not connected":
        raise HTTPException(400, "Gmail not connected. Please connect Gmail first.")
    
    return result


@router.get("/{business_id}/messages/{message_id}")
async def get_message(
    business_id: str,
    message_id: str,
    request: Request,
    format: str = Query("full", description="full, metadata, minimal, or raw")
):
    """
    Get a specific email with full details.
    
    Args:
        business_id: The business workspace
        message_id: Gmail message ID
        format: How much detail to return
        
    Returns:
        Full message object with headers, body, etc.
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    message = await gmail_service.get_message(
        business_id=business_id,
        message_id=message_id,
        format=format,
        ip_address=ip_address
    )
    
    if not message:
        raise HTTPException(404, "Message not found or Gmail not connected")
    
    return message


@router.post("/{business_id}/send", response_model=SendResponse)
async def send_email(
    business_id: str,
    email: SendEmailRequest,
    request: Request
):
    """
    Send an email from the connected Gmail account.
    
    Args:
        business_id: The business workspace
        email: Email details (to, subject, body, etc.)
        
    Returns:
        Sent message info or error
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    from shared.commercial import get_workspace_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    workspace_service = get_workspace_service(db)
    ip_address = request.client.host if request.client else None
    
    # Check quota before sending
    quota_check = await workspace_service.check_quota(business_id)
    if not quota_check.get("allowed", False):
        raise HTTPException(
            429, 
            f"Quota exceeded. Remaining: {quota_check.get('remaining', 0)} messages"
        )
    
    result = await gmail_service.send_email(
        business_id=business_id,
        to=email.to,
        subject=email.subject,
        body_text=email.body_text,
        body_html=email.body_html,
        cc=email.cc,
        bcc=email.bcc,
        reply_to_message_id=email.reply_to_message_id,
        thread_id=email.thread_id,
        ip_address=ip_address
    )
    
    if "error" in result:
        if result["error"] == "Gmail not connected":
            raise HTTPException(400, "Gmail not connected. Please connect Gmail first.")
        raise HTTPException(500, result["error"])
    
    return SendResponse(
        success=True,
        message_id=result.get("message_id"),
        thread_id=result.get("thread_id")
    )


@router.get("/{business_id}/labels")
async def get_labels(business_id: str, request: Request):
    """
    Get all Gmail labels for the connected account.
    
    Returns:
        List of labels with their IDs and types
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    labels = await gmail_service.get_labels(business_id, ip_address)
    
    if not labels:
        raise HTTPException(400, "Gmail not connected or no labels found")
    
    return {"labels": labels}


@router.post("/{business_id}/labels")
async def create_label(
    business_id: str,
    label: CreateLabelRequest,
    request: Request
):
    """
    Create a new Gmail label.
    
    Args:
        business_id: The business workspace
        label: Label details (name, visibility settings)
        
    Returns:
        Created label info
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    result = await gmail_service.create_label(
        business_id=business_id,
        name=label.name,
        label_list_visibility=label.label_list_visibility,
        message_list_visibility=label.message_list_visibility,
        ip_address=ip_address
    )
    
    if not result:
        raise HTTPException(500, "Failed to create label")
    
    return result


@router.put("/{business_id}/messages/{message_id}/read")
async def mark_as_read(
    business_id: str,
    message_id: str,
    request: Request
):
    """Mark a message as read"""
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    success = await gmail_service.mark_as_read(
        business_id=business_id,
        message_id=message_id,
        ip_address=ip_address
    )
    
    if not success:
        raise HTTPException(500, "Failed to mark as read")
    
    return {"success": True}


@router.put("/{business_id}/messages/{message_id}/unread")
async def mark_as_unread(
    business_id: str,
    message_id: str,
    request: Request
):
    """Mark a message as unread"""
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    success = await gmail_service.mark_as_unread(
        business_id=business_id,
        message_id=message_id,
        ip_address=ip_address
    )
    
    if not success:
        raise HTTPException(500, "Failed to mark as unread")
    
    return {"success": True}


@router.put("/{business_id}/messages/{message_id}/archive")
async def archive_message(
    business_id: str,
    message_id: str,
    request: Request
):
    """Archive a message (remove from inbox)"""
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    success = await gmail_service.archive_message(
        business_id=business_id,
        message_id=message_id,
        ip_address=ip_address
    )
    
    if not success:
        raise HTTPException(500, "Failed to archive message")
    
    return {"success": True}


@router.delete("/{business_id}/messages/{message_id}")
async def trash_message(
    business_id: str,
    message_id: str,
    request: Request
):
    """Move a message to trash"""
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    success = await gmail_service.trash_message(
        business_id=business_id,
        message_id=message_id,
        ip_address=ip_address
    )
    
    if not success:
        raise HTTPException(500, "Failed to trash message")
    
    return {"success": True}


@router.get("/{business_id}/profile", response_model=ProfileResponse)
async def get_profile(business_id: str, request: Request):
    """
    Get Gmail profile info for the connected account.
    
    Returns:
        Email address, message count, thread count
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    profile = await gmail_service.get_profile(business_id, ip_address)
    
    if not profile:
        raise HTTPException(400, "Gmail not connected")
    
    return ProfileResponse(
        email_address=profile.get("email_address", ""),
        messages_total=profile.get("messages_total", 0),
        threads_total=profile.get("threads_total", 0)
    )


@router.get("/{business_id}/threads/{thread_id}")
async def get_thread(
    business_id: str,
    thread_id: str,
    request: Request
):
    """
    Get a complete email thread with all messages.
    
    Args:
        business_id: The business workspace
        thread_id: Gmail thread ID
        
    Returns:
        Thread with all messages
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    thread = await gmail_service.get_thread(
        business_id=business_id,
        thread_id=thread_id,
        ip_address=ip_address
    )
    
    if not thread:
        raise HTTPException(404, "Thread not found or Gmail not connected")
    
    return thread


@router.get("/{business_id}/health")
async def health_check(business_id: str, request: Request):
    """
    Health check for Gmail connection.
    Tests if the connection is working by fetching the profile.
    """
    _require_owner_or_admin(business_id, request)  # Bug-fix #67
    from shared.commercial.gmail_service import get_gmail_service
    
    db = get_db()
    gmail_service = get_gmail_service(db)
    ip_address = request.client.host if request.client else None
    
    profile = await gmail_service.get_profile(business_id, ip_address)
    
    if profile:
        return {
            "status": "connected",
            "email": profile.get("email_address"),
            "messages_total": profile.get("messages_total", 0)
        }
    else:
        return {
            "status": "disconnected",
            "message": "Gmail not connected or token expired"
        }
