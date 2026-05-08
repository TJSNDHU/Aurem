"""
AUREM Commercial Platform - WhatsApp Cloud API Service
Handles WhatsApp Business API integration with Meta Embedded Signup

Features:
- Meta Embedded Signup OAuth flow
- WhatsApp webhook verification and message handling
- Send messages (text, templates, media)
- Phone number verification
- Integration with Unified Inbox
"""

import logging
import hmac
import hashlib
import httpx
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

logger = logging.getLogger(__name__)

# WhatsApp Cloud API Base URL
WHATSAPP_API_BASE = "https://graph.facebook.com/v21.0"


class WhatsAppMessageType(str, Enum):
    """WhatsApp message types"""
    TEXT = "text"
    TEMPLATE = "template"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    REACTION = "reaction"


class WhatsAppConnectionStatus(str, Enum):
    """Connection status"""
    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WhatsAppService:
    """
    WhatsApp Cloud API integration service.
    Supports Meta Embedded Signup for easy business onboarding.
    """
    
    COLLECTION = "aurem_whatsapp_connections"
    MESSAGES_COLLECTION = "aurem_whatsapp_messages"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION]
        self.messages = db[self.MESSAGES_COLLECTION]
        self.verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", f"aurem_verify_{secrets.token_hex(16)}")
        self.app_secret = os.environ.get("META_APP_SECRET", "")
    
    async def ensure_indexes(self):
        """Create database indexes"""
        await self.collection.create_index("business_id", unique=True)
        await self.collection.create_index("waba_id")
        await self.collection.create_index("phone_number_id")
        await self.messages.create_index("business_id")
        await self.messages.create_index("wa_message_id", unique=True)
        await self.messages.create_index([("business_id", 1), ("created_at", -1)])
        logger.info("[WhatsApp] Database indexes created")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # META EMBEDDED SIGNUP
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def initiate_embedded_signup(self, business_id: str) -> Dict[str, Any]:
        """
        Generate the OAuth URL for Meta Embedded Signup.
        
        The user will be redirected to Facebook to authorize the app
        and connect their WhatsApp Business Account.
        """
        app_id = os.environ.get("META_APP_ID", "")
        redirect_uri = os.environ.get("WHATSAPP_REDIRECT_URI", "")
        
        if not app_id:
            return {"error": "META_APP_ID not configured"}
        
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store pending connection
        await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "business_id": business_id,
                    "status": WhatsAppConnectionStatus.PENDING.value,
                    "oauth_state": state,
                    "initiated_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
        
        # Build OAuth URL for Embedded Signup
        oauth_url = (
            f"https://www.facebook.com/v21.0/dialog/oauth?"
            f"client_id={app_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope=whatsapp_business_management,whatsapp_business_messaging"
            f"&response_type=code"
            f"&extras={{\"feature\":\"whatsapp_embedded_signup\",\"version\":2}}"
        )
        
        return {
            "oauth_url": oauth_url,
            "state": state,
            "message": "Redirect user to oauth_url to begin WhatsApp connection"
        }
    
    async def complete_embedded_signup(
        self,
        business_id: str,
        code: str,
        state: str
    ) -> Dict[str, Any]:
        """
        Complete the Embedded Signup after OAuth callback.
        
        Exchanges the authorization code for access token and
        retrieves the WhatsApp Business Account (WABA) details.
        """
        # Verify state
        connection = await self.collection.find_one({"business_id": business_id})
        if not connection or connection.get("oauth_state") != state:
            return {"error": "Invalid state token - possible CSRF attack"}
        
        app_id = os.environ.get("META_APP_ID", "")
        app_secret = os.environ.get("META_APP_SECRET", "")
        redirect_uri = os.environ.get("WHATSAPP_REDIRECT_URI", "")
        
        if not all([app_id, app_secret]):
            return {"error": "META_APP_ID or META_APP_SECRET not configured"}
        
        try:
            async with httpx.AsyncClient() as client:
                # Exchange code for access token
                token_response = await client.get(
                    f"{WHATSAPP_API_BASE}/oauth/access_token",
                    params={
                        "client_id": app_id,
                        "client_secret": app_secret,
                        "redirect_uri": redirect_uri,
                        "code": code
                    }
                )
                
                if token_response.status_code != 200:
                    logger.error(f"[WhatsApp] Token exchange failed: {token_response.text}")
                    return {"error": "Failed to exchange authorization code"}
                
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                
                # Get WABA ID from the embedded signup response
                # The WABA ID and phone number ID come from the signup flow
                waba_id = token_data.get("waba_id")
                phone_number_id = token_data.get("phone_number_id")
                
                # If not in token response, fetch from debug_token
                if not waba_id:
                    debug_response = await client.get(
                        f"{WHATSAPP_API_BASE}/debug_token",
                        params={
                            "input_token": access_token,
                            "access_token": f"{app_id}|{app_secret}"
                        }
                    )
                    
                    if debug_response.status_code == 200:
                        debug_data = debug_response.json().get("data", {})
                        granular_scopes = debug_data.get("granular_scopes", [])
                        
                        for scope in granular_scopes:
                            if scope.get("scope") == "whatsapp_business_management":
                                target_ids = scope.get("target_ids", [])
                                if target_ids:
                                    waba_id = target_ids[0]
                                    break
                
                # Get phone numbers associated with WABA
                if waba_id:
                    phones_response = await client.get(
                        f"{WHATSAPP_API_BASE}/{waba_id}/phone_numbers",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    
                    if phones_response.status_code == 200:
                        phones_data = phones_response.json().get("data", [])
                        if phones_data:
                            phone_number_id = phones_data[0].get("id")
                            display_phone = phones_data[0].get("display_phone_number")
                
                # Update connection
                await self.collection.update_one(
                    {"business_id": business_id},
                    {
                        "$set": {
                            "status": WhatsAppConnectionStatus.CONNECTED.value,
                            "access_token": access_token,
                            "waba_id": waba_id,
                            "phone_number_id": phone_number_id,
                            "display_phone_number": display_phone if 'display_phone' in dir() else None,
                            "connected_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc)
                        },
                        "$unset": {"oauth_state": ""}
                    }
                )
                
                logger.info(f"[WhatsApp] Business {business_id} connected - WABA: {waba_id}")
                
                return {
                    "success": True,
                    "waba_id": waba_id,
                    "phone_number_id": phone_number_id,
                    "status": "connected"
                }
                
        except Exception as e:
            logger.error(f"[WhatsApp] Embedded signup failed: {e}")
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # WEBHOOK HANDLING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Verify webhook subscription request from Meta.
        
        Returns the challenge string if valid, None otherwise.
        """
        if mode == "subscribe" and token == self.verify_token:
            logger.info("[WhatsApp] Webhook verified successfully")
            return challenge
        
        logger.warning(f"[WhatsApp] Webhook verification failed - mode: {mode}, token match: {token == self.verify_token}")
        return None
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the X-Hub-Signature-256 header for incoming webhooks.
        
        Returns True if signature is valid.
        """
        if not self.app_secret:
            logger.warning("[WhatsApp] META_APP_SECRET not set - skipping signature verification")
            return True  # Allow in development
        
        if not signature or not signature.startswith("sha256="):
            return False
        
        expected_signature = signature.replace("sha256=", "")
        computed_signature = hmac.new(
            self.app_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, expected_signature)
    
    async def process_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming webhook payload from Meta.
        
        Handles:
        - messages: Incoming messages
        - statuses: Message delivery status updates
        """
        results = []
        
        try:
            # WhatsApp webhook structure
            entry = payload.get("entry", [])
            
            for e in entry:
                changes = e.get("changes", [])
                
                for change in changes:
                    field = change.get("field")
                    value = change.get("value", {})
                    
                    if field == "messages":
                        # Handle incoming messages
                        messages = value.get("messages", [])
                        contacts = value.get("contacts", [])
                        metadata = value.get("metadata", {})
                        
                        phone_number_id = metadata.get("phone_number_id")
                        
                        # Find business by phone_number_id
                        connection = await self.collection.find_one({
                            "phone_number_id": phone_number_id
                        })
                        
                        if not connection:
                            logger.warning(f"[WhatsApp] No connection found for phone_number_id: {phone_number_id}")
                            continue
                        
                        business_id = connection["business_id"]
                        
                        for msg in messages:
                            result = await self._handle_incoming_message(
                                business_id, msg, contacts, metadata
                            )
                            results.append(result)
                    
                    elif field == "statuses":
                        # Handle message status updates
                        statuses = value.get("statuses", [])
                        for status in statuses:
                            await self._handle_status_update(status)
            
            return {"processed": len(results), "results": results}
            
        except Exception as e:
            logger.error(f"[WhatsApp] Webhook processing error: {e}")
            return {"error": str(e)}
    
    async def _handle_incoming_message(
        self,
        business_id: str,
        message: Dict,
        contacts: List[Dict],
        metadata: Dict
    ) -> Dict[str, Any]:
        """Handle an incoming WhatsApp message"""
        wa_message_id = message.get("id")
        msg_type = message.get("type")
        timestamp = message.get("timestamp")
        from_number = message.get("from")
        
        # Get contact info
        contact = next((c for c in contacts if c.get("wa_id") == from_number), {})
        contact_name = contact.get("profile", {}).get("name", from_number)
        
        # Extract message content
        content = {}
        if msg_type == "text":
            content["text"] = message.get("text", {}).get("body", "")
        elif msg_type == "image":
            content["image"] = message.get("image", {})
        elif msg_type == "document":
            content["document"] = message.get("document", {})
        elif msg_type == "audio":
            content["audio"] = message.get("audio", {})
        elif msg_type == "video":
            content["video"] = message.get("video", {})
        elif msg_type == "location":
            content["location"] = message.get("location", {})
        elif msg_type == "contacts":
            content["contacts"] = message.get("contacts", [])
        elif msg_type == "interactive":
            content["interactive"] = message.get("interactive", {})
        elif msg_type == "button":
            content["button"] = message.get("button", {})
        
        # Store message
        msg_doc = {
            "wa_message_id": wa_message_id,
            "business_id": business_id,
            "direction": "inbound",
            "from_number": from_number,
            "contact_name": contact_name,
            "message_type": msg_type,
            "content": content,
            "timestamp": datetime.fromtimestamp(int(timestamp), tz=timezone.utc) if timestamp else datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "status": "received"
        }
        
        try:
            await self.messages.insert_one(msg_doc)
        except Exception as e:
            if "duplicate key" not in str(e).lower():
                raise
            return {"status": "duplicate", "wa_message_id": wa_message_id}
        
        # Ingest into Unified Inbox
        try:
            from services.aurem_commercial.unified_inbox_service import (
                get_unified_inbox_service, ChannelType
            )
            
            inbox_service = get_unified_inbox_service(self.db)
            
            await inbox_service.ingest_message(
                business_id=business_id,
                channel=ChannelType.WHATSAPP,
                external_id=wa_message_id,
                sender={
                    "name": contact_name,
                    "phone": from_number
                },
                content={
                    "body": content.get("text", f"[{msg_type}]"),
                    "type": msg_type,
                    "raw": content
                },
                metadata={
                    "phone_number_id": metadata.get("phone_number_id"),
                    "display_phone": metadata.get("display_phone_number")
                },
                auto_suggest=True
            )
            
            logger.info(f"[WhatsApp] Message {wa_message_id} ingested to Unified Inbox")
            
        except Exception as e:
            logger.warning(f"[WhatsApp] Failed to ingest to Unified Inbox: {e}")
        
        return {"status": "processed", "wa_message_id": wa_message_id, "type": msg_type}
    
    async def _handle_status_update(self, status: Dict):
        """Handle message status update (sent, delivered, read, failed)"""
        wa_message_id = status.get("id")
        status_value = status.get("status")  # sent, delivered, read, failed
        timestamp = status.get("timestamp")
        
        await self.messages.update_one(
            {"wa_message_id": wa_message_id},
            {
                "$set": {
                    "status": status_value,
                    "status_updated_at": datetime.fromtimestamp(int(timestamp), tz=timezone.utc) if timestamp else datetime.now(timezone.utc)
                }
            }
        )
        
        logger.debug(f"[WhatsApp] Message {wa_message_id} status: {status_value}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SEND MESSAGES
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def send_text_message(
        self,
        business_id: str,
        to_number: str,
        text: str,
        preview_url: bool = False
    ) -> Dict[str, Any]:
        """Send a text message via WhatsApp"""
        connection = await self.collection.find_one({"business_id": business_id})
        
        if not connection or connection.get("status") != WhatsAppConnectionStatus.CONNECTED.value:
            return {"error": "WhatsApp not connected"}
        
        access_token = connection.get("access_token")
        phone_number_id = connection.get("phone_number_id")
        
        if not all([access_token, phone_number_id]):
            return {"error": "Missing access token or phone number ID"}
        
        # Normalize phone number (remove + and spaces)
        to_number = to_number.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{WHATSAPP_API_BASE}/{phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": to_number,
                        "type": "text",
                        "text": {
                            "preview_url": preview_url,
                            "body": text
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    wa_message_id = result.get("messages", [{}])[0].get("id")
                    
                    # Store outbound message
                    await self.messages.insert_one({
                        "wa_message_id": wa_message_id,
                        "business_id": business_id,
                        "direction": "outbound",
                        "to_number": to_number,
                        "message_type": "text",
                        "content": {"text": text},
                        "created_at": datetime.now(timezone.utc),
                        "status": "sent"
                    })
                    
                    return {"success": True, "message_id": wa_message_id}
                else:
                    error = response.json().get("error", {})
                    logger.error(f"[WhatsApp] Send failed: {error}")
                    return {"error": error.get("message", "Failed to send message")}
                    
        except Exception as e:
            logger.error(f"[WhatsApp] Send error: {e}")
            return {"error": str(e)}
    
    async def send_template_message(
        self,
        business_id: str,
        to_number: str,
        template_name: str,
        language_code: str = "en_US",
        components: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Send a pre-approved template message"""
        connection = await self.collection.find_one({"business_id": business_id})
        
        if not connection or connection.get("status") != WhatsAppConnectionStatus.CONNECTED.value:
            return {"error": "WhatsApp not connected"}
        
        access_token = connection.get("access_token")
        phone_number_id = connection.get("phone_number_id")
        
        to_number = to_number.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": language_code}
                    }
                }
                
                if components:
                    payload["template"]["components"] = components
                
                response = await client.post(
                    f"{WHATSAPP_API_BASE}/{phone_number_id}/messages",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    wa_message_id = result.get("messages", [{}])[0].get("id")
                    return {"success": True, "message_id": wa_message_id}
                else:
                    error = response.json().get("error", {})
                    return {"error": error.get("message", "Failed to send template")}
                    
        except Exception as e:
            return {"error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_connection_status(self, business_id: str) -> Dict[str, Any]:
        """Get WhatsApp connection status for a business"""
        connection = await self.collection.find_one(
            {"business_id": business_id},
            {"_id": 0, "access_token": 0, "oauth_state": 0}
        )
        
        if not connection:
            return {
                "connected": False,
                "status": "not_configured"
            }
        
        return {
            "connected": connection.get("status") == WhatsAppConnectionStatus.CONNECTED.value,
            "status": connection.get("status"),
            "waba_id": connection.get("waba_id"),
            "phone_number_id": connection.get("phone_number_id"),
            "display_phone_number": connection.get("display_phone_number"),
            "connected_at": connection.get("connected_at")
        }
    
    async def disconnect(self, business_id: str) -> Dict[str, Any]:
        """Disconnect WhatsApp for a business"""
        result = await self.collection.update_one(
            {"business_id": business_id},
            {
                "$set": {
                    "status": WhatsAppConnectionStatus.DISCONNECTED.value,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$unset": {
                    "access_token": "",
                    "waba_id": "",
                    "phone_number_id": ""
                }
            }
        )
        
        return {"disconnected": result.modified_count > 0}
    
    async def get_message_history(
        self,
        business_id: str,
        phone_number: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get message history for a business"""
        query = {"business_id": business_id}
        
        if phone_number:
            phone_number = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            query["$or"] = [
                {"from_number": phone_number},
                {"to_number": phone_number}
            ]
        
        messages = await self.messages.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        return messages


# Singleton
_whatsapp_service: Optional[WhatsAppService] = None


def get_whatsapp_service(db: AsyncIOMotorDatabase) -> WhatsAppService:
    """Get or create WhatsApp service singleton"""
    global _whatsapp_service
    if _whatsapp_service is None:
        _whatsapp_service = WhatsAppService(db)
    return _whatsapp_service
