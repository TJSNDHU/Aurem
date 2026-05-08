"""
AUREM Commercial Platform - Unified Inbox Router
API endpoints for the command center inbox

Endpoints:
- GET /api/inbox/{business_id} - Get unified inbox messages
- GET /api/inbox/{business_id}/message/{message_id} - Get single message
- POST /api/inbox/{business_id}/ingest - Ingest a message (internal use)
- POST /api/inbox/{business_id}/message/{message_id}/approve - Approve suggestion
- POST /api/inbox/{business_id}/message/{message_id}/reject - Reject suggestion
- POST /api/inbox/{business_id}/message/{message_id}/archive - Archive message
- POST /api/inbox/{business_id}/message/{message_id}/regenerate - Regenerate suggestion
- POST /api/inbox/{business_id}/bulk-archive - Archive multiple messages
- GET /api/inbox/{business_id}/stats - Get inbox statistics
- GET /api/inbox/health - Health check
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Query, Header
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/inbox", tags=["AUREM Unified Inbox"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class SenderInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


class MessageContent(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None
    attachments: Optional[List[dict]] = None


class IngestMessageRequest(BaseModel):
    channel: str = Field(..., description="gmail, whatsapp, web_chat, sms")
    external_id: str = Field(..., description="Original message ID from channel")
    sender: SenderInfo
    content: MessageContent
    metadata: Optional[dict] = None
    auto_suggest: bool = True


class ApproveRequest(BaseModel):
    modified_params: Optional[dict] = None
    user_note: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None


class BulkArchiveRequest(BaseModel):
    message_ids: List[str]


class InboxStatsResponse(BaseModel):
    total: int = 0
    by_channel: dict = {}
    by_status: dict = {}
    pending_actions: int = 0


# ==================== ENDPOINTS ====================

@router.get("/health")
async def health():
    """Health check for Unified Inbox service"""
    return {
        "status": "healthy",
        "service": "aurem-unified-inbox",
        "capabilities": [
            "multi_channel_aggregation",
            "brain_suggestions",
            "action_approval",
            "real_time_updates"
        ]
    }


@router.get("/{business_id}")
async def get_inbox(
    business_id: str,
    request: Request,
    channel: Optional[str] = Query(None, description="Filter by channel: gmail, whatsapp, web_chat"),
    status: Optional[str] = Query(None, description="Filter by status: new, pending, suggested, actioned, archived"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False)
):
    """
    Get unified inbox messages for a business.
    
    Returns messages from all channels (Gmail, WhatsApp, Web Chat) in a single stream,
    sorted by received time (newest first). Each message includes Brain suggestions
    for quick action approval.
    """
    from services.aurem_commercial.unified_inbox_service import (
        get_unified_inbox_service, ChannelType, MessageStatus
    )
    
    inbox_service = get_unified_inbox_service(get_db())
    
    # Validate channel
    channel_enum = None
    if channel:
        try:
            channel_enum = ChannelType(channel)
        except ValueError:
            raise HTTPException(400, f"Invalid channel: {channel}. Valid: gmail, whatsapp, web_chat, sms")
    
    # Validate status
    status_enum = None
    if status:
        try:
            status_enum = MessageStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    
    result = await inbox_service.get_inbox(
        business_id=business_id,
        channel=channel_enum,
        status=status_enum,
        limit=limit,
        offset=offset,
        include_archived=include_archived
    )
    
    return result


@router.get("/{business_id}/message/{message_id}")
async def get_message(
    business_id: str,
    message_id: str,
    request: Request
):
    """
    Get a single inbox message with full details including Brain suggestion.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    message = await inbox_service.get_message(message_id)
    
    if not message:
        raise HTTPException(404, "Message not found")
    
    if message["business_id"] != business_id:
        raise HTTPException(403, "Access denied")
    
    return message


@router.post("/{business_id}/ingest")
async def ingest_message(
    business_id: str,
    data: IngestMessageRequest,
    request: Request
):
    """
    Ingest a message from any channel into the unified inbox.
    
    This endpoint is typically called internally when messages arrive
    via webhooks (Gmail Push, WhatsApp webhooks, etc.).
    
    Auto-generates a Brain suggestion by default.
    """
    from services.aurem_commercial.unified_inbox_service import (
        get_unified_inbox_service, ChannelType
    )
    
    inbox_service = get_unified_inbox_service(get_db())
    
    try:
        channel = ChannelType(data.channel)
    except ValueError:
        raise HTTPException(400, f"Invalid channel: {data.channel}")
    
    result = await inbox_service.ingest_message(
        business_id=business_id,
        channel=channel,
        external_id=data.external_id,
        sender=data.sender.dict(),
        content=data.content.dict(),
        metadata=data.metadata,
        auto_suggest=data.auto_suggest
    )
    
    return result


@router.post("/{business_id}/message/{message_id}/approve")
async def approve_suggestion(
    business_id: str,
    message_id: str,
    data: ApproveRequest,
    request: Request
):
    """
    Approve the Brain's suggested action for a message.
    
    This will execute the suggested action (e.g., send email, book appointment).
    You can optionally modify the action parameters before execution.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    result = await inbox_service.approve_suggestion(
        message_id=message_id,
        business_id=business_id,
        modified_params=data.modified_params,
        user_note=data.user_note
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/message/{message_id}/reject")
async def reject_suggestion(
    business_id: str,
    message_id: str,
    data: RejectRequest,
    request: Request
):
    """
    Reject the Brain's suggested action for a message.
    
    The message will be marked as rejected and you can provide a reason.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    result = await inbox_service.reject_suggestion(
        message_id=message_id,
        business_id=business_id,
        reason=data.reason
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/message/{message_id}/archive")
async def archive_message(
    business_id: str,
    message_id: str,
    request: Request
):
    """
    Archive an inbox message.
    
    Archived messages are hidden from the default inbox view but can be
    retrieved by setting include_archived=true.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    result = await inbox_service.archive_message(
        message_id=message_id,
        business_id=business_id
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/message/{message_id}/regenerate")
async def regenerate_suggestion(
    business_id: str,
    message_id: str,
    request: Request
):
    """
    Regenerate the Brain suggestion for a message.
    
    Useful if context has changed or you want a fresh analysis.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    result = await inbox_service.regenerate_suggestion(
        message_id=message_id,
        business_id=business_id
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/bulk-archive")
async def bulk_archive(
    business_id: str,
    data: BulkArchiveRequest,
    request: Request
):
    """
    Archive multiple inbox messages at once.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    result = await inbox_service.bulk_archive(
        business_id=business_id,
        message_ids=data.message_ids
    )
    
    return result


@router.get("/{business_id}/stats")
async def get_stats(
    business_id: str,
    request: Request
):
    """
    Get inbox statistics: total messages, by channel, by status, pending actions.
    """
    from services.aurem_commercial.unified_inbox_service import get_unified_inbox_service
    
    inbox_service = get_unified_inbox_service(get_db())
    
    # Get full inbox to calculate stats
    result = await inbox_service.get_inbox(
        business_id=business_id,
        limit=1,
        include_archived=True
    )
    
    return {
        "business_id": business_id,
        "stats": result["stats"]
    }


# ==================== SYNC ENDPOINTS ====================
# These endpoints sync messages from connected channels into the inbox

@router.post("/{business_id}/sync/gmail")
async def sync_gmail(
    business_id: str,
    request: Request,
    max_results: int = Query(20, ge=1, le=100)
):
    """
    Sync recent Gmail messages into the unified inbox.
    
    Fetches unread messages from Gmail and creates inbox entries with suggestions.
    """
    from services.aurem_commercial.gmail_service import get_gmail_service
    from services.aurem_commercial.unified_inbox_service import (
        get_unified_inbox_service, ChannelType
    )
    
    gmail_service = get_gmail_service(get_db())
    inbox_service = get_unified_inbox_service(get_db())
    ip_address = request.client.host if request.client else None
    
    # Fetch recent unread emails
    result = await gmail_service.list_messages(
        business_id=business_id,
        query="is:unread",
        max_results=max_results,
        label_ids=["INBOX", "UNREAD"],
        ip_address=ip_address
    )
    
    if "error" in result:
        raise HTTPException(400, result.get("error", "Gmail sync failed"))
    
    synced = []
    
    for msg_summary in result.get("messages", []):
        # Get full message
        message = await gmail_service.get_message(
            business_id=business_id,
            message_id=msg_summary["id"],
            ip_address=ip_address
        )
        
        if not message:
            continue
        
        # Ingest into unified inbox
        inbox_result = await inbox_service.ingest_message(
            business_id=business_id,
            channel=ChannelType.GMAIL,
            external_id=message["id"],
            sender={
                "name": message.get("from", "").split("<")[0].strip(),
                "email": message.get("from", "")
            },
            content={
                "subject": message.get("subject"),
                "body": message.get("body_text") or message.get("snippet"),
                "html": message.get("body_html")
            },
            metadata={
                "thread_id": message.get("thread_id"),
                "label_ids": message.get("label_ids", [])
            },
            auto_suggest=True
        )
        
        if not inbox_result.get("duplicate"):
            synced.append(inbox_result.get("message_id"))
    
    return {
        "synced_count": len(synced),
        "message_ids": synced,
        "total_available": result.get("result_size_estimate", 0)
    }
