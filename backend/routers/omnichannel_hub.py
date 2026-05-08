"""
AUREM Omnichannel Communications Hub
=====================================
Unified backend for WhatsApp (WHAPI), Live Chat, Email (Resend), and SMS.
All channels route through the Sovereign Brain (local Ollama) in Hybrid mode.
"""
import os
import logging
import httpx
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

router = APIRouter(prefix="/api/comms", tags=["Omnichannel"])
logger = logging.getLogger(__name__)

db = None

def set_db(database):
    global db
    db = database


def _get_db():
    global db
    if db is not None:
        return db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            db = server.db
            return db
    except Exception:
        pass
    return None


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(
            authorization.replace("Bearer ", ""),
            os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


async def _sovereign_brain(message: str, system_prompt: str = "", channel: str = "chat") -> dict:
    """
    Route a message through the Sovereign Brain (Hybrid: local Ollama first, cloud fallback).
    Returns {"response": str, "source": str, "latency_ms": int}
    """
    import time

    # Try local Ollama first
    try:
        from services.local_llm_service import chat_local, is_available, get_config
        cfg = get_config()
        if cfg.get("enabled"):
            avail = await asyncio.wait_for(is_available(), timeout=3.0)
            if avail:
                t0 = time.time()
                resp = await asyncio.wait_for(
                    chat_local(message=message, system_prompt=system_prompt),
                    timeout=30.0,
                )
                elapsed = int((time.time() - t0) * 1000)
                if resp and len(resp) > 5:
                    return {"response": resp, "source": f"sovereign_{cfg['model']}", "latency_ms": elapsed}
    except Exception as e:
        logger.debug(f"[Comms] Sovereign brain unavailable: {e}")

    # Fallback to cloud
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if key:
            import time as t
            t0 = t.time()
            chat = LlmChat(api_key=key, session_id=f"omni-{os.getpid()}", system_message=system_prompt or "You are AUREM ORA, a professional business AI assistant.")
            chat = chat.with_model("openai", "gpt-4o-mini")
            resp = await asyncio.wait_for(chat.send_message(UserMessage(text=message)), timeout=12.0)
            elapsed = int((t.time() - t0) * 1000)
            if resp:
                return {"response": resp, "source": "cloud_gpt4o-mini", "latency_ms": elapsed}
    except Exception as e:
        logger.warning(f"[Comms] Cloud fallback failed: {e}")

    return {"response": "I'm temporarily unable to process this request. Please try again shortly.", "source": "fallback", "latency_ms": 0}


# ═══════════════════════════════════════
# LIVE CHAT — Website visitor conversations
# ═══════════════════════════════════════

class LiveChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    visitor_name: Optional[str] = None
    visitor_email: Optional[str] = None
    page_url: Optional[str] = None


class LiveChatResponse(BaseModel):
    response: str
    session_id: str
    source: str
    latency_ms: int
    timestamp: str


@router.post("/chat", response_model=LiveChatResponse)
async def live_chat(req: LiveChatMessage):
    """
    Public endpoint — no auth required (for website widget).
    Routes visitor messages through the Sovereign Brain.
    """
    import secrets
    _db = _get_db()
    session_id = req.session_id or f"chat_{secrets.token_urlsafe(12)}"

    # Build context from chat history
    history_context = ""
    if _db and req.session_id:
        try:
            history = await _db.live_chat_messages.find(
                {"session_id": req.session_id},
                {"_id": 0, "role": 1, "content": 1}
            ).sort("timestamp", -1).limit(6).to_list(length=6)
            if history:
                history.reverse()
                history_context = "\n".join(f"{'Visitor' if m['role']=='user' else 'ORA'}: {m['content']}" for m in history)
        except Exception:
            pass

    system_prompt = (
        "You are ORA, the AI assistant for AUREM — a business automation platform. "
        "You're speaking with a website visitor. Be helpful, professional, and concise. "
        "If they ask about pricing, mention starting at $97 CAD/month. "
        "If they want a demo or to speak with a human, collect their name and email. "
        "If they have technical questions about their website, offer a free system scan."
    )
    if history_context:
        system_prompt += f"\n\nRecent conversation:\n{history_context}"

    result = await _sovereign_brain(req.message, system_prompt, channel="livechat")

    # Store messages
    if _db:
        try:
            now = datetime.now(timezone.utc).isoformat()
            await _db.live_chat_messages.insert_many([
                {"session_id": session_id, "role": "user", "content": req.message, "visitor_name": req.visitor_name, "visitor_email": req.visitor_email, "page_url": req.page_url, "timestamp": now},
                {"session_id": session_id, "role": "assistant", "content": result["response"], "source": result["source"], "timestamp": now},
            ])

            # If visitor provided email, capture as lead
            if req.visitor_email:
                await _db.comm_leads.update_one(
                    {"email": req.visitor_email},
                    {"$set": {"name": req.visitor_name, "email": req.visitor_email, "channel": "live_chat", "session_id": session_id, "updated_at": now},
                     "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
                # Auto-send First Contact email
                try:
                    from services.first_contact_email import auto_send_first_contact
                    asyncio.create_task(auto_send_first_contact(
                        _db, req.visitor_email, req.visitor_name or "there", "live_chat"
                    ))
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[LiveChat] DB store error: {e}")

    return LiveChatResponse(
        response=result["response"],
        session_id=session_id,
        source=result["source"],
        latency_ms=result["latency_ms"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/chat/sessions")
async def list_chat_sessions(limit: int = 20, authorization: str = Header(None)):
    """List recent live chat sessions (admin only)."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"sessions": []}

    pipeline = [
        {"$group": {
            "_id": "$session_id",
            "message_count": {"$sum": 1},
            "visitor_name": {"$first": "$visitor_name"},
            "visitor_email": {"$first": "$visitor_email"},
            "last_message": {"$last": "$content"},
            "last_timestamp": {"$max": "$timestamp"},
        }},
        {"$sort": {"last_timestamp": -1}},
        {"$limit": limit},
    ]
    sessions = await _db.live_chat_messages.aggregate(pipeline).to_list(length=limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/chat/session/{session_id}")
async def get_chat_session(session_id: str, authorization: str = Header(None)):
    """Get all messages in a chat session."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"messages": []}

    messages = await _db.live_chat_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(length=100)
    return {"session_id": session_id, "messages": messages}


# ═══════════════════════════════════════
# WHATSAPP — Via WHAPI
# ═══════════════════════════════════════

class WhatsAppInbound(BaseModel):
    """WHAPI webhook payload for incoming messages."""
    messages: Optional[List[Dict[str, Any]]] = None


class WhatsAppSend(BaseModel):
    to: str  # Phone number with country code
    message: str
    use_ai: bool = True  # Route through Sovereign Brain first


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """
    WHAPI webhook — receives incoming WhatsApp messages.
    Routes them through the Sovereign Brain and auto-replies.
    """
    _db = _get_db()
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    messages = body.get("messages", [])
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")

    for msg in messages:
        if msg.get("from_me"):
            continue

        sender = msg.get("chat_id", msg.get("from", ""))
        text = ""
        if msg.get("type") == "text":
            text = msg.get("text", {}).get("body", "")
        elif msg.get("type") == "chat":
            text = msg.get("body", "")

        if not text:
            continue

        logger.info(f"[WhatsApp] Incoming from {sender}: {text[:80]}")

        # Route through Sovereign Brain
        system_prompt = (
            "You are ORA, the AI assistant for AUREM. You're responding on WhatsApp. "
            "Be concise (under 300 chars when possible). Use a friendly, professional tone. "
            "If asked about pricing: $97 CAD/month starting. "
            "If asked for a demo: share the link aurem.live and offer to schedule a call."
        )
        result = await _sovereign_brain(text, system_prompt, channel="whatsapp")

        # Store conversation
        if _db:
            try:
                now = datetime.now(timezone.utc).isoformat()
                await _db.whatsapp_messages.insert_many([
                    {"chat_id": sender, "role": "user", "content": text, "timestamp": now},
                    {"chat_id": sender, "role": "assistant", "content": result["response"], "source": result["source"], "timestamp": now},
                ])
            except Exception:
                pass

        # Send reply via WHAPI
        if whapi_token:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(
                        "https://gate.whapi.cloud/messages/text",
                        headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                        json={"to": sender, "body": result["response"]},
                    )
                    logger.info(f"[WhatsApp] Replied to {sender} via {result['source']}")
            except Exception as e:
                logger.warning(f"[WhatsApp] Send failed: {e}")
        else:
            logger.warning("[WhatsApp] WHAPI_API_TOKEN not set — reply not sent")

    return {"ok": True}


@router.post("/whatsapp/send")
async def send_whatsapp(req: WhatsAppSend, authorization: str = Header(None)):
    """Send a WhatsApp message (optionally AI-enhanced)."""
    await _auth(authorization)
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    if not whapi_token:
        raise HTTPException(status_code=503, detail="WHAPI_API_TOKEN not configured. Inject via Empire HUD.")

    message = req.message
    source = "manual"

    if req.use_ai:
        result = await _sovereign_brain(
            f"Rewrite this message for WhatsApp (concise, professional): {req.message}",
            "You are a professional copywriter. Rewrite the given message for WhatsApp delivery. Keep it under 300 characters.",
            channel="whatsapp"
        )
        message = result["response"]
        source = result["source"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {whapi_token}", "Content-Type": "application/json"},
                json={"to": req.to, "body": message},
            )
            return {"success": resp.status_code == 200, "message_sent": message, "source": source, "to": req.to}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/whatsapp/conversations")
async def list_whatsapp_conversations(limit: int = 20, authorization: str = Header(None)):
    """List recent WhatsApp conversations."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"conversations": []}

    pipeline = [
        {"$group": {
            "_id": "$chat_id",
            "message_count": {"$sum": 1},
            "last_message": {"$last": "$content"},
            "last_role": {"$last": "$role"},
            "last_timestamp": {"$max": "$timestamp"},
        }},
        {"$sort": {"last_timestamp": -1}},
        {"$limit": limit},
    ]
    convos = await _db.whatsapp_messages.aggregate(pipeline).to_list(length=limit)
    return {"conversations": convos, "total": len(convos)}


@router.get("/whatsapp/verify")
async def verify_whatsapp_connection(authorization: str = Header(None)):
    """
    Verify WHAPI token is working. Tests the connection to WhatsApp API.
    Call this after injecting the WHAPI token via Empire HUD.
    """
    await _auth(authorization)
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    if not whapi_token:
        return {
            "connected": False,
            "error": "WHAPI_API_TOKEN not configured",
            "action": "Inject your WHAPI token via Empire HUD → WhatsApp node",
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://gate.whapi.cloud/settings",
                headers={"Authorization": f"Bearer {whapi_token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "phone": data.get("phone", ""),
                    "name": data.get("pushname", data.get("name", "")),
                    "platform": data.get("platform", ""),
                    "webhook_url": f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/comms/whatsapp/webhook",
                    "message": "WhatsApp connected! Set the webhook URL above in your WHAPI dashboard.",
                }
            else:
                return {
                    "connected": False,
                    "error": f"WHAPI returned HTTP {resp.status_code}: {resp.text[:200]}",
                    "action": "Check your WHAPI token is correct",
                }
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ═══════════════════════════════════════
# UNIFIED INBOX — Cross-channel view
# ═══════════════════════════════════════

@router.get("/inbox")
async def unified_inbox(limit: int = 30, authorization: str = Header(None)):
    """Unified inbox — shows recent messages across all channels."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"messages": [], "channels": {}}

    # Aggregate from all channels
    chat_msgs = await _db.live_chat_messages.find(
        {"role": "user"}, {"_id": 0, "session_id": 1, "content": 1, "visitor_name": 1, "visitor_email": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(limit).to_list(length=limit)

    wa_msgs = await _db.whatsapp_messages.find(
        {"role": "user"}, {"_id": 0, "chat_id": 1, "content": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(limit).to_list(length=limit)

    # Tag channels
    for m in chat_msgs:
        m["channel"] = "live_chat"
        m["sender"] = m.get("visitor_name") or m.get("visitor_email") or m.get("session_id", "")[:12]
    for m in wa_msgs:
        m["channel"] = "whatsapp"
        m["sender"] = m.get("chat_id", "")

    # Merge and sort
    all_msgs = sorted(chat_msgs + wa_msgs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

    # Channel counts
    chat_count = await _db.live_chat_messages.count_documents({"role": "user"})
    wa_count = await _db.whatsapp_messages.count_documents({"role": "user"})
    lead_count = await _db.comm_leads.count_documents({})

    return {
        "messages": all_msgs,
        "channels": {
            "live_chat": chat_count,
            "whatsapp": wa_count,
        },
        "total_leads": lead_count,
    }


@router.get("/leads")
async def list_leads(limit: int = 50, authorization: str = Header(None)):
    """List all captured leads from all channels."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"leads": []}

    leads = await _db.comm_leads.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"leads": leads, "total": len(leads)}


# ═══════════════════════════════════════════════════════════
# TELEGRAM CHANNEL (DeerFlow Pattern)
# ═══════════════════════════════════════════════════════════

class TelegramMessage(BaseModel):
    chat_id: str
    text: str


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram messages via webhook, route through ORA Sovereign Brain."""
    _db = _get_db()
    try:
        body = await request.json()
        message = body.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        username = message.get("from", {}).get("username", "")
        first_name = message.get("from", {}).get("first_name", "")

        if not text or not chat_id:
            return {"ok": True}

        # Route through Sovereign Brain
        system_prompt = f"ORA responding via Telegram to {first_name or username}. Be concise and direct. No markdown."
        result = await _sovereign_brain(text, system_prompt, channel="telegram")
        ai_response = result.get("response", "I'll look into that.")

        # Save to DB
        now = datetime.now(timezone.utc)
        if _db:
            await _db.telegram_messages.insert_many([
                {"chat_id": chat_id, "role": "user", "text": text, "username": username, "timestamp": now.isoformat()},
                {"chat_id": chat_id, "role": "assistant", "text": ai_response, "timestamp": now.isoformat()},
            ])

        # Send reply via Telegram Bot API
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if bot_token:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={"chat_id": chat_id, "text": ai_response},
                )

        return {"ok": True}

    except Exception as e:
        logger.warning(f"[Telegram] Webhook error: {e}")
        return {"ok": True}


@router.post("/telegram/send")
async def send_telegram(req: TelegramMessage, authorization: str = Header(None)):
    """Send a message to a Telegram chat. Requires auth."""
    await _auth(authorization)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="TELEGRAM_BOT_TOKEN not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": req.chat_id, "text": req.text},
            )
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telegram/conversations")
async def list_telegram_conversations(limit: int = 20, authorization: str = Header(None)):
    """List recent Telegram conversations."""
    await _auth(authorization)
    _db = _get_db()
    if not _db:
        return {"conversations": []}
    pipeline = [
        {"$group": {"_id": "$chat_id", "last_message": {"$last": "$text"}, "username": {"$last": "$username"},
                     "count": {"$sum": 1}, "last_at": {"$max": "$timestamp"}}},
        {"$sort": {"last_at": -1}},
        {"$limit": limit},
    ]
    convos = await _db.telegram_messages.aggregate(pipeline).to_list(limit)
    return {"conversations": [{**c, "chat_id": c["_id"]} for c in convos], "count": len(convos)}
