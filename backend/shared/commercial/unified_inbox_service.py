"""
AUREM Commercial Platform - Unified Inbox Service
Aggregates all communication channels into a single stream with AI-powered suggestions

Features:
- Unified view of Gmail, WhatsApp, Web Chat messages
- Brain-powered action suggestions for each message
- Real-time updates via WebSocket
- Message status tracking (pending, suggested, actioned, archived)
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class ChannelType(str, Enum):
    """Communication channel types"""
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    WEB_CHAT = "web_chat"
    SMS = "sms"


class MessageStatus(str, Enum):
    """Unified message status"""
    NEW = "new"                     # Just received, not processed
    PENDING = "pending"             # Awaiting Brain suggestion
    SUGGESTED = "suggested"         # Brain has suggested an action
    APPROVED = "approved"           # User approved the suggestion
    ACTIONED = "actioned"           # Action executed
    ARCHIVED = "archived"           # Archived/dismissed
    REJECTED = "rejected"           # Suggestion rejected


class UnifiedInboxService:
    """
    Central inbox that aggregates all channels.
    Each message gets a Brain suggestion for quick action.
    """
    
    COLLECTION = "aurem_unified_inbox"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION]
    
    async def ensure_indexes(self):
        """Create database indexes"""
        await self.collection.create_index("business_id")
        await self.collection.create_index("channel")
        await self.collection.create_index("status")
        await self.collection.create_index("received_at")
        await self.collection.create_index([
            ("business_id", 1),
            ("received_at", -1)
        ])
        await self.collection.create_index([
            ("business_id", 1),
            ("external_id", 1),
            ("channel", 1)
        ], unique=True)
        logger.info("[UnifiedInbox] Indexes created")
    
    async def ingest_message(
        self,
        business_id: str,
        channel: ChannelType,
        external_id: str,
        sender: Dict[str, Any],
        content: Dict[str, Any],
        metadata: Optional[Dict] = None,
        auto_suggest: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest a message from any channel into the unified inbox.
        
        Args:
            business_id: Business workspace ID
            channel: Source channel (gmail, whatsapp, web_chat)
            external_id: Original message ID from the channel
            sender: Sender info {name, email/phone, avatar_url}
            content: Message content {subject, body, attachments}
            metadata: Channel-specific metadata
            auto_suggest: Whether to run Brain suggestion automatically
            
        Returns:
            Created inbox message with suggestion if requested
        """
        message_id = f"inbox_{secrets.token_hex(10)}"
        now = datetime.now(timezone.utc)
        
        # Check for duplicate
        existing = await self.collection.find_one({
            "business_id": business_id,
            "external_id": external_id,
            "channel": channel.value
        })
        
        if existing:
            logger.info(f"[UnifiedInbox] Duplicate message {external_id} skipped")
            return {"message_id": existing["message_id"], "duplicate": True}
        
        message_doc = {
            "message_id": message_id,
            "business_id": business_id,
            "channel": channel.value,
            "external_id": external_id,
            "sender": sender,
            "content": content,
            "metadata": metadata or {},
            "status": MessageStatus.NEW.value,
            "received_at": now,
            "updated_at": now,
            "brain_suggestion": None,
            "action_history": []
        }
        
        await self.collection.insert_one(message_doc)
        logger.info(f"[UnifiedInbox] Ingested {channel.value} message {message_id}")
        
        # Run Brain suggestion if requested
        if auto_suggest:
            try:
                suggestion = await self._generate_suggestion(business_id, message_doc)
                if suggestion:
                    await self.collection.update_one(
                        {"message_id": message_id},
                        {
                            "$set": {
                                "brain_suggestion": suggestion,
                                "status": MessageStatus.SUGGESTED.value,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                    message_doc["brain_suggestion"] = suggestion
                    message_doc["status"] = MessageStatus.SUGGESTED.value
            except Exception as e:
                logger.warning(f"[UnifiedInbox] Brain suggestion failed: {e}")
        
        # Push to WebSocket
        await self._push_new_message(business_id, message_doc)
        
        # Return without _id
        message_doc.pop("_id", None)
        return message_doc
    
    async def _generate_suggestion(
        self,
        business_id: str,
        message: Dict
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a Brain suggestion for a message.
        Uses the Brain Orchestrator's OODA loop.
        """
        try:
            from services.aurem_commercial.brain_orchestrator import (
                get_brain_orchestrator, BrainInput
            )
            
            brain = get_brain_orchestrator(self.db)
            
            # Construct message for Brain
            channel = message["channel"]
            sender = message["sender"]
            content = message["content"]
            
            # Build context string
            context_str = f"[{channel.upper()}] From: {sender.get('name', sender.get('email', sender.get('phone', 'Unknown')))}"
            if content.get("subject"):
                context_str += f"\nSubject: {content['subject']}"
            context_str += f"\nMessage: {content.get('body', content.get('text', ''))[:500]}"
            
            # Create minimal key info for internal processing
            key_info = {
                "key_id": "internal_inbox",
                "business_id": business_id,
                "scopes": ["chat:read", "chat:write", "actions:email", "actions:calendar", "actions:payments", "actions:whatsapp"]
            }
            
            result = await brain.think(
                business_id=business_id,
                input_data=BrainInput(
                    message=context_str,
                    context={"channel": channel, "inbox_message_id": message["message_id"]}
                ),
                api_key_info=key_info
            )
            
            # Extract suggestion from result
            orient = result.phases.get("orient", {})
            decide = result.phases.get("decide", {})
            
            return {
                "thought_id": result.thought_id,
                "intent": orient.get("intent", "chat"),
                "confidence": orient.get("confidence", 0.5),
                "suggested_action": decide.get("selected_tool"),
                "action_params": decide.get("tool_parameters", {}),
                "draft_response": decide.get("response_draft"),
                "reasoning": orient.get("reasoning", ""),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[UnifiedInbox] Suggestion generation failed: {e}")
            return None
    
    async def _push_new_message(self, business_id: str, message: Dict):
        """Push new message notification to WebSocket"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            
            # Clean message for WebSocket
            ws_message = {
                "message_id": message["message_id"],
                "channel": message["channel"],
                "sender": message["sender"],
                "preview": message["content"].get("body", message["content"].get("text", ""))[:100],
                "subject": message["content"].get("subject"),
                "status": message["status"],
                "has_suggestion": message.get("brain_suggestion") is not None,
                "received_at": message["received_at"].isoformat() if isinstance(message["received_at"], datetime) else message["received_at"]
            }
            
            await hub.broadcast_to_business(business_id, {
                "type": "inbox_message",
                "action": "new",
                "message": ws_message
            })
        except Exception as e:
            logger.warning(f"[UnifiedInbox] WebSocket push failed: {e}")
    
    async def get_inbox(
        self,
        business_id: str,
        channel: Optional[ChannelType] = None,
        status: Optional[MessageStatus] = None,
        limit: int = 50,
        offset: int = 0,
        include_archived: bool = False
    ) -> Dict[str, Any]:
        """
        Get unified inbox messages for a business.
        
        Args:
            business_id: Business workspace ID
            channel: Filter by channel (optional)
            status: Filter by status (optional)
            limit: Max messages to return
            offset: Pagination offset
            include_archived: Include archived messages
            
        Returns:
            List of inbox messages with pagination
        """
        query = {"business_id": business_id}
        
        if channel:
            query["channel"] = channel.value
        
        if status:
            query["status"] = status.value
        elif not include_archived:
            query["status"] = {"$nin": [MessageStatus.ARCHIVED.value]}
        
        total = await self.collection.count_documents(query)
        
        messages = await self.collection.find(
            query,
            {"_id": 0}
        ).sort("received_at", -1).skip(offset).limit(limit).to_list(limit)
        
        # Calculate stats
        stats = await self._get_inbox_stats(business_id)
        
        return {
            "messages": messages,
            "total": total,
            "limit": limit,
            "offset": offset,
            "stats": stats
        }
    
    async def _get_inbox_stats(self, business_id: str) -> Dict[str, Any]:
        """Get inbox statistics"""
        pipeline = [
            {"$match": {"business_id": business_id}},
            {"$group": {
                "_id": {
                    "channel": "$channel",
                    "status": "$status"
                },
                "count": {"$sum": 1}
            }}
        ]
        
        results = await self.collection.aggregate(pipeline).to_list(100)
        
        stats = {
            "total": 0,
            "by_channel": {},
            "by_status": {},
            "pending_actions": 0
        }
        
        for r in results:
            channel = r["_id"]["channel"]
            status = r["_id"]["status"]
            count = r["count"]
            
            stats["total"] += count
            stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + count
            stats["by_status"][status] = stats["by_status"].get(status, 0) + count
            
            if status in [MessageStatus.SUGGESTED.value, MessageStatus.APPROVED.value]:
                stats["pending_actions"] += count
        
        return stats
    
    async def get_message(self, message_id: str) -> Optional[Dict]:
        """Get a single inbox message"""
        return await self.collection.find_one(
            {"message_id": message_id},
            {"_id": 0}
        )
    
    async def approve_suggestion(
        self,
        message_id: str,
        business_id: str,
        modified_params: Optional[Dict] = None,
        user_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve a Brain suggestion for a message.
        This will execute the suggested action.
        
        Args:
            message_id: Inbox message ID
            business_id: Business ID for verification
            modified_params: Override action parameters (optional)
            user_note: User's note on the action
            
        Returns:
            Action result
        """
        message = await self.get_message(message_id)
        
        if not message:
            return {"error": "Message not found"}
        
        if message["business_id"] != business_id:
            return {"error": "Access denied"}
        
        suggestion = message.get("brain_suggestion")
        if not suggestion:
            return {"error": "No suggestion available"}
        
        # Execute the action
        action_tool = suggestion.get("suggested_action")
        action_params = modified_params or suggestion.get("action_params", {})
        
        action_result = None
        
        if action_tool:
            try:
                from services.aurem_commercial.action_engine import get_action_engine
                engine = get_action_engine(self.db)
                
                result = await engine.handle_tool_call(
                    business_id=business_id,
                    func=action_tool,
                    args=action_params
                )
                
                action_result = result
                
            except Exception as e:
                logger.error(f"[UnifiedInbox] Action execution failed: {e}")
                action_result = {"error": str(e)}
        
        # Update message status
        await self.collection.update_one(
            {"message_id": message_id},
            {
                "$set": {
                    "status": MessageStatus.ACTIONED.value,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "action_history": {
                        "action": "approved",
                        "tool": action_tool,
                        "params": action_params,
                        "result": action_result,
                        "user_note": user_note,
                        "timestamp": datetime.now(timezone.utc)
                    }
                }
            }
        )
        
        # Push update to WebSocket
        await self._push_status_update(business_id, message_id, "actioned")
        
        return {
            "success": True,
            "action": action_tool,
            "result": action_result
        }
    
    async def reject_suggestion(
        self,
        message_id: str,
        business_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reject a Brain suggestion"""
        message = await self.get_message(message_id)
        
        if not message or message["business_id"] != business_id:
            return {"error": "Message not found or access denied"}
        
        await self.collection.update_one(
            {"message_id": message_id},
            {
                "$set": {
                    "status": MessageStatus.REJECTED.value,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {
                    "action_history": {
                        "action": "rejected",
                        "reason": reason,
                        "timestamp": datetime.now(timezone.utc)
                    }
                }
            }
        )
        
        await self._push_status_update(business_id, message_id, "rejected")
        
        return {"success": True}
    
    async def archive_message(
        self,
        message_id: str,
        business_id: str
    ) -> Dict[str, Any]:
        """Archive an inbox message"""
        result = await self.collection.update_one(
            {"message_id": message_id, "business_id": business_id},
            {
                "$set": {
                    "status": MessageStatus.ARCHIVED.value,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count == 0:
            return {"error": "Message not found"}
        
        await self._push_status_update(business_id, message_id, "archived")
        
        return {"success": True}
    
    async def regenerate_suggestion(
        self,
        message_id: str,
        business_id: str
    ) -> Dict[str, Any]:
        """Regenerate Brain suggestion for a message"""
        message = await self.get_message(message_id)
        
        if not message or message["business_id"] != business_id:
            return {"error": "Message not found or access denied"}
        
        suggestion = await self._generate_suggestion(business_id, message)
        
        if suggestion:
            await self.collection.update_one(
                {"message_id": message_id},
                {
                    "$set": {
                        "brain_suggestion": suggestion,
                        "status": MessageStatus.SUGGESTED.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            await self._push_status_update(business_id, message_id, "suggested")
            
            return {"success": True, "suggestion": suggestion}
        
        return {"error": "Failed to generate suggestion"}
    
    async def _push_status_update(self, business_id: str, message_id: str, status: str):
        """Push status update to WebSocket"""
        try:
            from services.aurem_commercial import get_websocket_hub
            hub = await get_websocket_hub()
            
            await hub.broadcast_to_business(business_id, {
                "type": "inbox_message",
                "action": "update",
                "message_id": message_id,
                "status": status
            })
        except Exception:
            pass
    
    async def bulk_archive(
        self,
        business_id: str,
        message_ids: List[str]
    ) -> Dict[str, Any]:
        """Archive multiple messages"""
        result = await self.collection.update_many(
            {"message_id": {"$in": message_ids}, "business_id": business_id},
            {
                "$set": {
                    "status": MessageStatus.ARCHIVED.value,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return {"archived_count": result.modified_count}


# Singleton
_inbox_service: Optional[UnifiedInboxService] = None


def get_unified_inbox_service(db: AsyncIOMotorDatabase) -> UnifiedInboxService:
    """Get or create the Unified Inbox service"""
    global _inbox_service
    if _inbox_service is None:
        _inbox_service = UnifiedInboxService(db)
    return _inbox_service
