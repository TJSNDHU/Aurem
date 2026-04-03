"""
Live Support Router - AI-First Support System
Flow: AI Chat -> Callback Request -> Admin Screen Share Request
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json
import logging
import uuid
import os
import httpx

router = APIRouter(prefix="/api/support", tags=["Live Support"])

# OpenRouter config for AI chat
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# In-memory stores (use Redis in production)
active_sessions: Dict[str, dict] = {}
pending_invites: Dict[str, dict] = {}
callback_requests: Dict[str, dict] = {}  # Callback queue
chat_connections: Dict[str, WebSocket] = {}  # user_id -> chat websocket

# WebSocket connections
user_connections: Dict[str, WebSocket] = {}  # user_id -> websocket
admin_connections: Dict[str, WebSocket] = {}  # admin_id -> websocket

# Cache for AI responses
ai_response_cache: Dict[str, str] = {}
error_diagnosis_cache: Dict[str, str] = {}


class SupportSessionManager:
    """Manages live support sessions"""
    
    @staticmethod
    def create_session(user_id: str, user_name: str) -> dict:
        session_id = str(uuid.uuid4())[:8]
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "user_name": user_name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "has_camera": False,
            "has_screen": False,
            "viewing_admins": []
        }
        active_sessions[session_id] = session
        return session
    
    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        return active_sessions.get(session_id)
    
    @staticmethod
    def get_user_session(user_id: str) -> Optional[dict]:
        for session in active_sessions.values():
            if session["user_id"] == user_id and session["status"] == "active":
                return session
        return None
    
    @staticmethod
    def end_session(session_id: str):
        if session_id in active_sessions:
            active_sessions[session_id]["status"] = "ended"
            active_sessions[session_id]["ended_at"] = datetime.now(timezone.utc).isoformat()
    
    @staticmethod
    def get_active_sessions() -> List[dict]:
        return [s for s in active_sessions.values() if s["status"] == "active"]


manager = SupportSessionManager()


# Helper function to broadcast to all admins
async def broadcast_to_admins(data: dict):
    """Send a message to all connected admin WebSockets"""
    for admin_id, ws in list(admin_connections.items()):
        try:
            await ws.send_json(data)
        except Exception as e:
            logging.error(f"[SUPPORT] Failed to broadcast to admin {admin_id}: {e}")


# ============ REST Endpoints ============

@router.post("/start")
async def start_support_session(request: Request):
    """User initiates a support session"""
    try:
        body = await request.json()
        user_id = body.get("user_id")
        user_name = body.get("user_name", "Anonymous")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        # Check if user already has active session
        existing = manager.get_user_session(user_id)
        if existing:
            return existing
        
        session = manager.create_session(user_id, user_name)
        
        # Notify all connected admins
        await broadcast_to_admins({
            "type": "new_session",
            "session": session
        })
        
        logging.info(f"[SUPPORT] Session started: {session['session_id']} for user {user_name}")
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[SUPPORT] Start session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/end/{session_id}")
async def end_support_session(session_id: str):
    """End a support session"""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    manager.end_session(session_id)
    
    # Notify admins
    await broadcast_to_admins({
        "type": "session_ended",
        "session_id": session_id
    })
    
    # Disconnect user websocket
    if session["user_id"] in user_connections:
        try:
            await user_connections[session["user_id"]].close()
        except:
            pass
        del user_connections[session["user_id"]]
    
    logging.info(f"[SUPPORT] Session ended: {session_id}")
    return {"status": "ended", "session_id": session_id}


@router.get("/sessions")
async def get_active_sessions():
    """Get all active support sessions (admin only)"""
    return {"sessions": manager.get_active_sessions()}


@router.get("/session/{session_id}")
async def get_session_details(session_id: str):
    """Get details of a specific session"""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ============ INVITE LINK SYSTEM ============

@router.post("/invite/create")
async def create_invite_link(request: Request):
    """Admin creates an invite link to share with customer"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id", "admin")
        customer_name = body.get("customer_name", "")
        customer_email = body.get("customer_email", "")
        note = body.get("note", "")
        
        # Generate unique invite code
        invite_code = str(uuid.uuid4())[:8].upper()
        
        invite = {
            "invite_code": invite_code,
            "created_by": admin_id,
            "customer_name": customer_name,
            "customer_email": customer_email,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",  # pending, used, expired
            "expires_at": None,  # Could add expiry
            "session_id": None  # Set when user joins
        }
        
        pending_invites[invite_code] = invite
        
        logging.info(f"[SUPPORT] Invite created: {invite_code} by {admin_id}")
        return {
            "invite_code": invite_code,
            "invite_url": f"/app?support={invite_code}",
            "full_url": f"{{origin}}/app?support={invite_code}",
            "invite": invite
        }
        
    except Exception as e:
        logging.error(f"[SUPPORT] Create invite error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invite/{invite_code}")
async def get_invite(invite_code: str):
    """Get invite details (used by customer when clicking link)"""
    invite = pending_invites.get(invite_code.upper())
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")
    
    if invite["status"] == "used":
        raise HTTPException(status_code=400, detail="Invite already used")
    
    return invite


@router.post("/invite/{invite_code}/join")
async def join_via_invite(invite_code: str, request: Request):
    """Customer joins support session via invite link"""
    try:
        body = await request.json()
        user_id = body.get("user_id", f"guest-{uuid.uuid4().hex[:6]}")
        user_name = body.get("user_name", "Guest")
        
        invite = pending_invites.get(invite_code.upper())
        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")
        
        if invite["status"] == "used":
            raise HTTPException(status_code=400, detail="Invite already used")
        
        # Create session for this invite
        session = manager.create_session(user_id, user_name or invite.get("customer_name", "Customer"))
        
        # Update invite status
        invite["status"] = "used"
        invite["session_id"] = session["session_id"]
        invite["joined_at"] = datetime.now(timezone.utc).isoformat()
        
        # Notify admins
        await broadcast_to_admins({
            "type": "invite_joined",
            "invite_code": invite_code,
            "session": session
        })
        
        logging.info(f"[SUPPORT] Invite {invite_code} joined, session: {session['session_id']}")
        return {"session": session, "invite": invite}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[SUPPORT] Join invite error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invites")
async def list_invites():
    """List all pending invites (admin)"""
    return {
        "invites": [inv for inv in pending_invites.values() if inv["status"] == "pending"]
    }


# ============ AI CHAT SUPPORT ============

@router.post("/chat")
async def ai_chat_support(request: Request):
    """AI-powered chat support - first line of defense"""
    try:
        body = await request.json()
        user_id = body.get("user_id", "anonymous")
        user_name = body.get("user_name", "Customer")
        message = body.get("message", "")
        context = body.get("context", [])
        
        if not message:
            raise HTTPException(status_code=400, detail="Message required")
        
        # Build conversation context
        system_prompt = """You are ReRoots AI Support Assistant for a biotech skincare e-commerce store.

STORE INFO:
- ReRoots sells Korean biotech skincare (AURA-GEN series)
- Products: TXA+PDRN Serum ($89.99), Accelerator Cream ($74.99), Recovery Complex ($99.99)
- Free shipping on orders over $50 CAD
- 30-day return policy for unopened products
- Loyalty points: Silver (0-999), Gold (1000-2999), Diamond (3000+)

COMMON ISSUES & SOLUTIONS:
- Order tracking: Ask for order number, provide tracking link
- Product recommendations: Ask about skin concerns
- Returns: Explain 30-day policy, provide return form link
- Account issues: Suggest password reset or contact support

RULES:
1. Be friendly, concise, and helpful
2. If you CAN'T resolve the issue after 2-3 exchanges, say "I'd recommend speaking with our team directly" and set show_callback=true
3. Never make up information about orders or products
4. Keep responses under 100 words
5. Use simple language, avoid jargon"""

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation context
        for ctx in context[-4:]:  # Last 4 messages for context
            messages.append(ctx)
        
        messages.append({"role": "user", "content": message})
        
        show_callback = False
        response_text = "I apologize, I'm having trouble right now. Would you like to speak with our support team?"
        
        logging.info(f"[AI Chat] OpenRouter API Key present: {bool(OPENROUTER_API_KEY)}")
        
        if OPENROUTER_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    logging.info(f"[AI Chat] Sending request to OpenRouter...")
                    response = await client.post(
                        OPENROUTER_BASE_URL,
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://reroots.ca",
                            "X-Title": "ReRoots AI Support"
                        },
                        json={
                            "model": "google/gemini-2.0-flash-lite-001",
                            "messages": messages,
                            "max_tokens": 300,
                            "temperature": 0.7
                        }
                    )
                    
                    logging.info(f"[AI Chat] OpenRouter response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        response_text = data.get("choices", [{}])[0].get("message", {}).get("content", response_text)
                        logging.info(f"[AI Chat] AI response received: {response_text[:100]}...")
                        
                        # Check if AI suggests callback
                        if any(phrase in response_text.lower() for phrase in [
                            "speak with our team", "contact support", "human agent",
                            "callback", "call you back", "speak directly"
                        ]):
                            show_callback = True
                    else:
                        logging.error(f"[AI Chat] OpenRouter error response: {response.text}")
                            
            except Exception as e:
                logging.error(f"[AI Chat] OpenRouter error: {e}")
                show_callback = True
        else:
            # No API key - suggest callback
            show_callback = True
            response_text = "I'd be happy to help! For the best assistance, would you like to request a callback from our team?"
        
        return {
            "response": response_text,
            "show_callback": show_callback,
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[AI Chat] Error: {e}")
        return {
            "response": "I'm sorry, something went wrong. Would you like to speak with our support team?",
            "show_callback": True
        }


# ============ CALLBACK SYSTEM ============

@router.post("/callback/request")
async def request_callback(request: Request):
    """User requests a callback from support team"""
    try:
        body = await request.json()
        user_id = body.get("user_id", f"guest-{uuid.uuid4().hex[:6]}")
        user_name = body.get("user_name", "Guest")
        user_email = body.get("user_email", "")
        phone = body.get("phone", "")
        note = body.get("note", "")
        chat_history = body.get("chat_history", [])
        
        callback_id = str(uuid.uuid4())[:8]
        
        callback = {
            "callback_id": callback_id,
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
            "phone": phone,
            "note": note,
            "chat_history": chat_history[-10:],  # Last 10 messages
            "status": "pending",  # pending, in_progress, completed, cancelled
            "created_at": datetime.now(timezone.utc).isoformat(),
            "assigned_admin": None
        }
        
        callback_requests[callback_id] = callback
        
        # Notify all admins
        await broadcast_to_admins({
            "type": "new_callback",
            "callback": callback
        })
        
        logging.info(f"[SUPPORT] Callback requested: {callback_id} from {user_name}")
        return {"callback_id": callback_id, "status": "pending", "message": "Callback request received"}
        
    except Exception as e:
        logging.error(f"[SUPPORT] Callback request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/callbacks")
async def get_callback_requests():
    """Get all pending callback requests (admin)"""
    return {
        "callbacks": [cb for cb in callback_requests.values() if cb["status"] == "pending"]
    }


@router.post("/callback/{callback_id}/accept")
async def accept_callback(callback_id: str, request: Request):
    """Admin accepts a callback request"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id")
        admin_name = body.get("admin_name", "Support Team")
        
        callback = callback_requests.get(callback_id)
        if not callback:
            raise HTTPException(status_code=404, detail="Callback not found")
        
        callback["status"] = "in_progress"
        callback["assigned_admin"] = admin_id
        callback["accepted_at"] = datetime.now(timezone.utc).isoformat()
        
        # Notify user via WebSocket if connected
        user_id = callback["user_id"]
        if user_id in chat_connections:
            try:
                await chat_connections[user_id].send_json({
                    "type": "callback_accepted",
                    "admin_name": admin_name,
                    "callback_id": callback_id
                })
            except:
                pass
        
        logging.info(f"[SUPPORT] Callback {callback_id} accepted by {admin_name}")
        return {"status": "accepted", "callback": callback}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[SUPPORT] Accept callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ ADMIN-INITIATED SCREEN SHARE ============

@router.post("/screen-share/request")
async def request_screen_share(request: Request):
    """Admin requests screen share from user"""
    try:
        body = await request.json()
        admin_id = body.get("admin_id")
        admin_name = body.get("admin_name", "Support Team")
        user_id = body.get("user_id")
        message = body.get("message", "Our support team would like to view your screen to help diagnose the issue.")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        
        # Create a session for this screen share
        session_id = str(uuid.uuid4())[:8]
        
        # Send request to user via WebSocket
        if user_id in chat_connections:
            await chat_connections[user_id].send_json({
                "type": "screen_share_request",
                "session_id": session_id,
                "admin_id": admin_id,
                "admin_name": admin_name,
                "message": message
            })
            logging.info(f"[SUPPORT] Screen share request sent to {user_id}")
            return {"status": "sent", "session_id": session_id}
        else:
            raise HTTPException(status_code=404, detail="User not connected")
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[SUPPORT] Screen share request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screen-share/decline")
async def decline_screen_share(request: Request):
    """User declines screen share request"""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        user_id = body.get("user_id")
        
        # Notify admin that user declined
        await broadcast_to_admins({
            "type": "screen_share_declined",
            "session_id": session_id,
            "user_id": user_id
        })
        
        logging.info(f"[SUPPORT] Screen share declined by {user_id}")
        return {"status": "declined"}
        
    except Exception as e:
        logging.error(f"[SUPPORT] Decline screen share error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ CHAT WEBSOCKET ============

@router.websocket("/ws/chat/{user_id}")
async def chat_websocket(websocket: WebSocket, user_id: str):
    """WebSocket for user chat - receives admin notifications"""
    await websocket.accept()
    chat_connections[user_id] = websocket
    
    logging.info(f"[SUPPORT] Chat WebSocket connected: {user_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            # Handle any user-sent messages if needed
            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        logging.info(f"[SUPPORT] Chat WebSocket disconnected: {user_id}")
    except Exception as e:
        logging.error(f"[SUPPORT] Chat WS error: {e}")
    finally:
        if user_id in chat_connections:
            del chat_connections[user_id]

async def get_ai_error_diagnosis(error_text: str) -> str:
    """Send error to OpenRouter for AI diagnosis"""
    
    # Check cache first
    cache_key = error_text[:200]  # Use first 200 chars as cache key
    if cache_key in error_diagnosis_cache:
        return error_diagnosis_cache[cache_key]
    
    if not OPENROUTER_API_KEY:
        return "AI diagnosis unavailable - OpenRouter not configured"
    
    try:
        prompt = f"""You are a senior frontend developer helping debug a customer's web application issue.

Analyze this console error and provide a brief, actionable diagnosis:

ERROR: {error_text}

Respond in this format:
**Issue**: [One sentence explaining what went wrong]
**Likely Cause**: [Most probable cause]
**Fix**: [Quick actionable fix for the support team]

Keep it under 100 words. Be practical and direct."""

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://reroots.ca",
                    "X-Title": "ReRoots Support AI"
                },
                json={
                    "model": "meta-llama/llama-3.3-70b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.3
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                diagnosis = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Cache the result
                error_diagnosis_cache[cache_key] = diagnosis
                return diagnosis
            else:
                logging.error(f"[AI] OpenRouter error: {response.status_code}")
                return f"AI diagnosis failed (status {response.status_code})"
                
    except Exception as e:
        logging.error(f"[AI] Diagnosis error: {e}")
        return f"AI diagnosis error: {str(e)}"


@router.post("/diagnose-error")
async def diagnose_error(request: Request):
    """Get AI diagnosis for a console error"""
    try:
        body = await request.json()
        error_text = body.get("error", "")
        
        if not error_text:
            raise HTTPException(status_code=400, detail="error text required")
        
        diagnosis = await get_ai_error_diagnosis(error_text)
        return {"diagnosis": diagnosis, "error": error_text[:200]}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[AI] Diagnose endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ WebSocket Endpoints ============

async def broadcast_to_admins(message: dict):
    """Send message to all connected admins"""
    disconnected = []
    for admin_id, ws in admin_connections.items():
        try:
            await ws.send_json(message)
        except:
            disconnected.append(admin_id)
    for admin_id in disconnected:
        del admin_connections[admin_id]


@router.websocket("/ws/user/{session_id}")
async def user_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket for user to stream rrweb events and WebRTC signaling
    """
    await websocket.accept()
    
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return
    
    user_id = session["user_id"]
    user_connections[user_id] = websocket
    
    logging.info(f"[SUPPORT] User connected: {session_id}")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "rrweb_events":
                # Forward rrweb events to viewing admins
                session["has_screen"] = True
                events = data.get("events", [])
                logging.info(f"[SUPPORT] Received {len(events)} rrweb events from session {session_id}")
                
                viewing_admins = session.get("viewing_admins", [])
                logging.info(f"[SUPPORT] Forwarding to {len(viewing_admins)} viewing admins: {viewing_admins}")
                
                for admin_id in viewing_admins:
                    if admin_id in admin_connections:
                        try:
                            await admin_connections[admin_id].send_json({
                                "type": "rrweb_events",
                                "session_id": session_id,
                                "events": events
                            })
                            logging.info(f"[SUPPORT] Sent events to admin {admin_id}")
                        except Exception as e:
                            logging.error(f"[SUPPORT] Failed to send to admin {admin_id}: {e}")
            
            elif msg_type == "webrtc_offer":
                # Forward WebRTC offer to admin (camera or screen)
                stream_type = data.get("stream_type", "camera")
                if stream_type == "screen":
                    session["has_screen"] = True
                else:
                    session["has_camera"] = True
                target_admin = data.get("target_admin")
                logging.info(f"[SUPPORT] Forwarding WebRTC offer ({stream_type}) to admin {target_admin}")
                if target_admin and target_admin in admin_connections:
                    await admin_connections[target_admin].send_json({
                        "type": "webrtc_offer",
                        "session_id": session_id,
                        "offer": data.get("offer"),
                        "stream_type": stream_type
                    })
            
            elif msg_type == "webrtc_ice":
                # Forward ICE candidate to admin
                target_admin = data.get("target_admin")
                stream_type = data.get("stream_type", "camera")
                if target_admin and target_admin in admin_connections:
                    await admin_connections[target_admin].send_json({
                        "type": "webrtc_ice",
                        "session_id": session_id,
                        "candidate": data.get("candidate"),
                        "stream_type": stream_type
                    })
            
            elif msg_type == "console_error":
                # Forward console errors to admins WITH AI diagnosis
                error_text = data.get("error", "")
                timestamp = data.get("timestamp")
                
                # Get AI diagnosis asynchronously
                diagnosis = await get_ai_error_diagnosis(error_text)
                
                for admin_id in session.get("viewing_admins", []):
                    if admin_id in admin_connections:
                        try:
                            await admin_connections[admin_id].send_json({
                                "type": "console_error",
                                "session_id": session_id,
                                "error": error_text,
                                "timestamp": timestamp,
                                "ai_diagnosis": diagnosis
                            })
                        except:
                            pass
                            
    except WebSocketDisconnect:
        logging.info(f"[SUPPORT] User disconnected: {session_id}")
    except Exception as e:
        logging.error(f"[SUPPORT] User WS error: {e}")
    finally:
        if user_id in user_connections:
            del user_connections[user_id]
        # Auto-end session when user disconnects
        manager.end_session(session_id)
        await broadcast_to_admins({
            "type": "session_ended",
            "session_id": session_id
        })


@router.websocket("/ws/admin/{admin_id}")
async def admin_websocket(websocket: WebSocket, admin_id: str):
    """
    WebSocket for admin to receive live streams and send WebRTC signaling
    """
    await websocket.accept()
    admin_connections[admin_id] = websocket
    
    logging.info(f"[SUPPORT] Admin connected: {admin_id}")
    
    # Send current active sessions
    await websocket.send_json({
        "type": "active_sessions",
        "sessions": manager.get_active_sessions()
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "watch_session":
                # Admin wants to watch a session
                session_id = data.get("session_id")
                session = manager.get_session(session_id)
                if session:
                    if admin_id not in session["viewing_admins"]:
                        session["viewing_admins"].append(admin_id)
                    logging.info(f"[SUPPORT] Admin {admin_id} now watching session {session_id}")
                    logging.info(f"[SUPPORT] Session viewing_admins: {session['viewing_admins']}")
                    # Notify user to start streaming
                    user_id = session["user_id"]
                    if user_id in user_connections:
                        await user_connections[user_id].send_json({
                            "type": "admin_watching",
                            "admin_id": admin_id
                        })
                        logging.info(f"[SUPPORT] Notified user {user_id} that admin is watching")
                    else:
                        logging.warning(f"[SUPPORT] User {user_id} not connected via WebSocket")
            
            elif msg_type == "stop_watching":
                # Admin stops watching a session
                session_id = data.get("session_id")
                session = manager.get_session(session_id)
                if session and admin_id in session["viewing_admins"]:
                    session["viewing_admins"].remove(admin_id)
            
            elif msg_type == "webrtc_answer":
                # Forward WebRTC answer to user
                session_id = data.get("session_id")
                session = manager.get_session(session_id)
                stream_type = data.get("stream_type", "camera")
                if session:
                    user_id = session["user_id"]
                    if user_id in user_connections:
                        await user_connections[user_id].send_json({
                            "type": "webrtc_answer",
                            "answer": data.get("answer"),
                            "admin_id": admin_id,
                            "stream_type": stream_type
                        })
            
            elif msg_type == "webrtc_ice":
                # Forward ICE candidate to user
                session_id = data.get("session_id")
                session = manager.get_session(session_id)
                stream_type = data.get("stream_type", "camera")
                if session:
                    user_id = session["user_id"]
                    if user_id in user_connections:
                        await user_connections[user_id].send_json({
                            "type": "webrtc_ice",
                            "candidate": data.get("candidate"),
                            "admin_id": admin_id,
                            "stream_type": stream_type
                        })
                            
    except WebSocketDisconnect:
        logging.info(f"[SUPPORT] Admin disconnected: {admin_id}")
    except Exception as e:
        logging.error(f"[SUPPORT] Admin WS error: {e}")
    finally:
        if admin_id in admin_connections:
            del admin_connections[admin_id]
        # Remove admin from all viewing lists
        for session in active_sessions.values():
            if admin_id in session.get("viewing_admins", []):
                session["viewing_admins"].remove(admin_id)
