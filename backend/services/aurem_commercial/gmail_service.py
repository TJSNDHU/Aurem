"""
AUREM Commercial Platform - Gmail Service
Business logic for Gmail integration (read/send emails)

Features:
- Read emails from connected Gmail accounts
- Send emails on behalf of connected accounts
- Label management
- Email search and filtering
- Thread management
"""

import base64
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.discovery import build
from motor.motor_asyncio import AsyncIOMotorDatabase

from .token_vault import get_token_vault, IntegrationProvider
from .audit_service import get_audit_logger, AuditAction
from .workspace_service import get_workspace_service

logger = logging.getLogger(__name__)


class GmailService:
    """
    Gmail service for reading and sending emails.
    Uses OAuth tokens stored in TokenVault.
    """
    
    COLLECTION_NAME = "aurem_gmail_messages"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION_NAME]
        self.token_vault = get_token_vault(db)
        self.audit = get_audit_logger(db)
        self.workspace_service = get_workspace_service(db)
    
    async def ensure_indexes(self):
        """Create database indexes for message caching"""
        await self.collection.create_index("business_id")
        await self.collection.create_index("message_id")
        await self.collection.create_index("thread_id")
        await self.collection.create_index([
            ("business_id", 1),
            ("message_id", 1)
        ], unique=True)
        await self.collection.create_index("received_at")
        logger.info("[GmailService] Indexes created")
    
    async def _get_credentials(
        self,
        business_id: str,
        ip_address: Optional[str] = None
    ) -> Optional[Credentials]:
        """
        Get Gmail credentials from TokenVault and refresh if needed.
        
        Returns:
            Google Credentials object or None if not connected
        """
        token_data = await self.token_vault.get_credentials(
            business_id=business_id,
            provider=IntegrationProvider.GOOGLE,
            purpose="gmail_api_call",
            ip_address=ip_address
        )
        
        if not token_data:
            logger.warning(f"[GmailService] No Google credentials for {business_id}")
            return None
        
        creds_dict = token_data["credentials"]
        
        # Build credentials object
        creds = Credentials(
            token=creds_dict.get("access_token"),
            refresh_token=creds_dict.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds_dict.get("client_id"),
            client_secret=creds_dict.get("client_secret")
        )
        
        # Check if token needs refresh
        expires_at = token_data.get("expires_at")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if datetime.now(timezone.utc) >= expires_at:
                logger.info(f"[GmailService] Refreshing token for {business_id}")
                try:
                    creds.refresh(GoogleRequest())
                    
                    # Update token in vault
                    await self.token_vault.store_integration(
                        business_id=business_id,
                        provider=IntegrationProvider.GOOGLE,
                        credentials={
                            "access_token": creds.token,
                            "refresh_token": creds.refresh_token,
                            "client_id": creds_dict.get("client_id"),
                            "client_secret": creds_dict.get("client_secret")
                        },
                        expires_at=creds.expiry,
                        ip_address=ip_address
                    )
                except Exception as e:
                    logger.error(f"[GmailService] Token refresh failed: {e}")
                    await self.token_vault.record_error(
                        business_id, IntegrationProvider.GOOGLE, str(e)
                    )
                    return None
        
        return creds
    
    def _build_service(self, creds: Credentials):
        """Build Gmail API service"""
        return build('gmail', 'v1', credentials=creds)
    
    async def list_messages(
        self,
        business_id: str,
        query: Optional[str] = None,
        max_results: int = 20,
        page_token: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List emails from the connected Gmail account.
        
        Args:
            business_id: The business workspace
            query: Gmail search query (e.g., "from:customer@example.com")
            max_results: Maximum messages to return (default 20)
            page_token: Pagination token
            label_ids: Filter by label IDs (e.g., ["INBOX", "UNREAD"])
            ip_address: Request IP for audit
            
        Returns:
            Dict with messages list and pagination info
        """
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return {"error": "Gmail not connected", "messages": []}
        
        try:
            service = self._build_service(creds)
            
            # Build request
            kwargs = {
                "userId": "me",
                "maxResults": max_results
            }
            
            if query:
                kwargs["q"] = query
            if page_token:
                kwargs["pageToken"] = page_token
            if label_ids:
                kwargs["labelIds"] = label_ids
            
            result = service.users().messages().list(**kwargs).execute()
            
            messages = result.get("messages", [])
            next_page_token = result.get("nextPageToken")
            
            # Track usage
            await self.workspace_service.increment_usage(
                business_id=business_id,
                metric="gmail_reads",
                count=1
            )
            
            # Audit
            await self.audit.log(
                action=AuditAction.DATA_ACCESSED,
                business_id=business_id,
                actor_type="system",
                resource_type="gmail_messages",
                details={
                    "query": query,
                    "count": len(messages)
                },
                ip_address=ip_address,
                success=True
            )
            
            return {
                "messages": messages,
                "next_page_token": next_page_token,
                "result_size_estimate": result.get("resultSizeEstimate", 0)
            }
            
        except Exception as e:
            logger.error(f"[GmailService] List messages failed: {e}")
            await self.token_vault.record_error(
                business_id, IntegrationProvider.GOOGLE, str(e)
            )
            return {"error": str(e), "messages": []}
    
    async def get_message(
        self,
        business_id: str,
        message_id: str,
        format: str = "full",
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific email message with full details.
        
        Args:
            business_id: The business workspace
            message_id: Gmail message ID
            format: "full", "metadata", "minimal", or "raw"
            ip_address: Request IP for audit
            
        Returns:
            Full message object or None
        """
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return None
        
        try:
            service = self._build_service(creds)
            
            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format=format
            ).execute()
            
            # Parse headers for easier access
            headers = {}
            for header in message.get("payload", {}).get("headers", []):
                headers[header["name"].lower()] = header["value"]
            
            # Extract body
            body_text = ""
            body_html = ""
            
            payload = message.get("payload", {})
            if "body" in payload and payload["body"].get("data"):
                body_text = base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="ignore")
            
            # Handle multipart
            for part in payload.get("parts", []):
                mime_type = part.get("mimeType", "")
                if part.get("body", {}).get("data"):
                    decoded = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="ignore")
                    
                    if mime_type == "text/plain":
                        body_text = decoded
                    elif mime_type == "text/html":
                        body_html = decoded
            
            return {
                "id": message.get("id"),
                "thread_id": message.get("threadId"),
                "label_ids": message.get("labelIds", []),
                "snippet": message.get("snippet"),
                "internal_date": message.get("internalDate"),
                "headers": headers,
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "body_text": body_text,
                "body_html": body_html,
                "size_estimate": message.get("sizeEstimate", 0)
            }
            
        except Exception as e:
            logger.error(f"[GmailService] Get message failed: {e}")
            return None
    
    async def send_email(
        self,
        business_id: str,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to_message_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email from the connected Gmail account.
        
        Args:
            business_id: The business workspace
            to: Recipient email
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body
            cc: CC recipients
            bcc: BCC recipients
            reply_to_message_id: Original message ID for replies
            thread_id: Thread ID for conversation threading
            ip_address: Request IP for audit
            
        Returns:
            Sent message info or error
        """
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return {"error": "Gmail not connected"}
        
        try:
            service = self._build_service(creds)
            
            # Get connected email
            profile = service.users().getProfile(userId="me").execute()
            from_email = profile.get("emailAddress")
            
            # Build message
            if body_html:
                message = MIMEMultipart("alternative")
                message.attach(MIMEText(body_text, "plain"))
                message.attach(MIMEText(body_html, "html"))
            else:
                message = MIMEText(body_text, "plain")
            
            message["to"] = to
            message["from"] = from_email
            message["subject"] = subject
            
            if cc:
                message["cc"] = ", ".join(cc)
            if bcc:
                message["bcc"] = ", ".join(bcc)
            
            # Handle reply threading
            if reply_to_message_id:
                # Get original message headers
                original = await self.get_message(
                    business_id, reply_to_message_id, format="metadata"
                )
                if original:
                    message["In-Reply-To"] = original["headers"].get("message-id", "")
                    message["References"] = original["headers"].get("message-id", "")
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode("utf-8")
            
            # Send
            body = {"raw": raw_message}
            if thread_id:
                body["threadId"] = thread_id
            
            result = service.users().messages().send(
                userId="me",
                body=body
            ).execute()
            
            # Track usage
            await self.workspace_service.increment_usage(
                business_id=business_id,
                metric="gmail_sends",
                count=1
            )
            
            # Also count as AI interaction if this was AI-generated
            await self.workspace_service.increment_usage(
                business_id=business_id,
                metric="ai_interactions",
                count=1
            )
            
            # Audit
            await self.audit.log(
                action=AuditAction.EMAIL_SENT,
                business_id=business_id,
                actor_type="system",
                resource_type="gmail_message",
                resource_id=result.get("id"),
                details={
                    "to": to,
                    "subject": subject,
                    "thread_id": result.get("threadId"),
                    "is_reply": bool(reply_to_message_id)
                },
                ip_address=ip_address,
                success=True
            )
            
            return {
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "label_ids": result.get("labelIds", [])
            }
            
        except Exception as e:
            logger.error(f"[GmailService] Send email failed: {e}")
            await self.token_vault.record_error(
                business_id, IntegrationProvider.GOOGLE, str(e)
            )
            return {"error": str(e)}
    
    async def get_labels(
        self,
        business_id: str,
        ip_address: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all Gmail labels for the connected account"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return []
        
        try:
            service = self._build_service(creds)
            result = service.users().labels().list(userId="me").execute()
            return result.get("labels", [])
        except Exception as e:
            logger.error(f"[GmailService] Get labels failed: {e}")
            return []
    
    async def create_label(
        self,
        business_id: str,
        name: str,
        label_list_visibility: str = "labelShow",
        message_list_visibility: str = "show",
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new Gmail label"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return None
        
        try:
            service = self._build_service(creds)
            result = service.users().labels().create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": label_list_visibility,
                    "messageListVisibility": message_list_visibility
                }
            ).execute()
            
            return result
        except Exception as e:
            logger.error(f"[GmailService] Create label failed: {e}")
            return None
    
    async def apply_label(
        self,
        business_id: str,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """Add or remove labels from a message"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return False
        
        try:
            service = self._build_service(creds)
            
            body = {}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids
            
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body=body
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"[GmailService] Apply label failed: {e}")
            return False
    
    async def mark_as_read(
        self,
        business_id: str,
        message_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Mark a message as read"""
        return await self.apply_label(
            business_id=business_id,
            message_id=message_id,
            remove_label_ids=["UNREAD"],
            ip_address=ip_address
        )
    
    async def mark_as_unread(
        self,
        business_id: str,
        message_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Mark a message as unread"""
        return await self.apply_label(
            business_id=business_id,
            message_id=message_id,
            add_label_ids=["UNREAD"],
            ip_address=ip_address
        )
    
    async def archive_message(
        self,
        business_id: str,
        message_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Archive a message (remove from inbox)"""
        return await self.apply_label(
            business_id=business_id,
            message_id=message_id,
            remove_label_ids=["INBOX"],
            ip_address=ip_address
        )
    
    async def trash_message(
        self,
        business_id: str,
        message_id: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Move message to trash"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return False
        
        try:
            service = self._build_service(creds)
            service.users().messages().trash(
                userId="me",
                id=message_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"[GmailService] Trash message failed: {e}")
            return False
    
    async def get_profile(
        self,
        business_id: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get Gmail profile info (email address, history ID, etc.)"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return None
        
        try:
            service = self._build_service(creds)
            profile = service.users().getProfile(userId="me").execute()
            return {
                "email_address": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal"),
                "threads_total": profile.get("threadsTotal"),
                "history_id": profile.get("historyId")
            }
        except Exception as e:
            logger.error(f"[GmailService] Get profile failed: {e}")
            return None
    
    async def get_thread(
        self,
        business_id: str,
        thread_id: str,
        ip_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a complete email thread"""
        creds = await self._get_credentials(business_id, ip_address)
        if not creds:
            return None
        
        try:
            service = self._build_service(creds)
            thread = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full"
            ).execute()
            
            return {
                "id": thread.get("id"),
                "history_id": thread.get("historyId"),
                "messages": thread.get("messages", [])
            }
        except Exception as e:
            logger.error(f"[GmailService] Get thread failed: {e}")
            return None


# Singleton
_gmail_service: Optional[GmailService] = None


def get_gmail_service(db: AsyncIOMotorDatabase) -> GmailService:
    """Get or create the Gmail service instance"""
    global _gmail_service
    if _gmail_service is None:
        _gmail_service = GmailService(db)
    return _gmail_service
