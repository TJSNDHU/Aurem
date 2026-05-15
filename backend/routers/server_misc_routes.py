"""
Server Misc Routes — Inline routes extracted from server.py
Includes: WebSocket, SSE, User Address, Password Reset, Phone Login,
          Product CRUD, Admin AI Assistant, WhatsApp Validate.
"""

import os
import asyncio
import uuid
import logging
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from collections import deque

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)

# Module-level state — set via set_deps()
_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"
_ws_manager = None


def set_deps(database, jwt_secret, jwt_algorithm, ws_mgr):
    global _db, _jwt_secret, _jwt_algorithm, _ws_manager
    _db = database
    _jwt_secret = jwt_secret
    _jwt_algorithm = jwt_algorithm
    _ws_manager = ws_mgr


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════
# AUTH HELPERS (local copies)
# ═══════════════════════════

async def _get_current_user(request: Request) -> Optional[dict]:
    db = _get_db()
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth_header[7:], _jwt_secret, algorithms=[_jwt_algorithm])
        user_id = payload.get("user_id")
        if user_id and db:
            return await db.users.find_one({"id": user_id}, {"_id": 0})
    except Exception:
        pass
    return None


async def _require_admin(request: Request) -> dict:
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not (user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ═══════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for real-time updates"""
    client_id = str(uuid.uuid4())
    user_id = None
    is_admin = False

    try:
        token = websocket.query_params.get("token")
        if token:
            try:
                db = _get_db()
                payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
                user_id = payload.get("user_id")
                if user_id and db:
                    user = await db.users.find_one({"id": user_id}, {"_id": 0})
                    if user:
                        is_admin = user.get("is_admin", False) or user.get("is_super_admin", False)
            except jwt.InvalidTokenError:
                pass

        if _ws_manager:
            await _ws_manager.connect(websocket, client_id, user_id, is_admin)

        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "is_admin": is_admin,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})
                elif data.get("type") == "subscribe":
                    channel = data.get("channel")
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": channel,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            except Exception:
                break

    except WebSocketDisconnect:
        if _ws_manager:
            await _ws_manager.disconnect(client_id)
    except Exception:
        if _ws_manager:
            await _ws_manager.disconnect(client_id)


@router.get("/admin/websocket/status")
async def get_websocket_status(request: Request):
    """Get WebSocket connection statistics (admin only)"""
    await _require_admin(request)
    return {
        "connections": _ws_manager.get_connection_count() if _ws_manager else 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ═══════════════════════════
# SSE (Server-Sent Events)
# ═══════════════════════════

_sse_queues: Dict[str, asyncio.Queue] = {}
_recent_events: deque = deque(maxlen=50)


async def push_sse_event(event_type: str, data: dict):
    """Call this from anywhere to push a live event to all SSE clients."""
    import json as _json
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _recent_events.append(event)
    for q in list(_sse_queues.values()):
        try:
            await q.put(event)
        except Exception:
            pass


async def _sse_stream(client_id: str):
    """Generate SSE events for a client."""
    import json as _json
    q = asyncio.Queue()
    _sse_queues[client_id] = q

    try:
        yield f"data: {_json.dumps({'type': 'connected', 'clientId': client_id})}\n\n"
        for old_event in list(_recent_events)[-10:]:
            yield f"data: {_json.dumps(old_event)}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield f"data: {_json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield f": heartbeat {datetime.now(timezone.utc).isoformat()}\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        _sse_queues.pop(client_id, None)


@router.get("/admin/events/{client_id}")
async def sse_events(client_id: str, request: Request):
    """Server-Sent Events endpoint"""
    return StreamingResponse(
        _sse_stream(client_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": os.environ.get("CORS_PRIMARY", "https://aurem.live"),
        }
    )


# ═══════════════════════════
# USER ADDRESS ENDPOINTS
# ═══════════════════════════

class UserAddressUpdate(BaseModel):
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    province: str
    postal_code: str
    country: str = "CA"


@router.get("/users/me/address")
async def get_user_address(request: Request):
    """Get the current user's saved shipping address"""
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = _get_db()
    user_data = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    shipping_address = user_data.get("shipping_address", {})
    return {
        "address_line1": shipping_address.get("address_line1", ""),
        "address_line2": shipping_address.get("address_line2", ""),
        "city": shipping_address.get("city", ""),
        "province": shipping_address.get("province", ""),
        "postal_code": shipping_address.get("postal_code", ""),
        "country": shipping_address.get("country", "CA"),
    }


@router.put("/users/me/address")
async def update_user_address(address: UserAddressUpdate, request: Request):
    """Update the current user's shipping address"""
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = _get_db()
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "shipping_address": {
                "address_line1": address.address_line1,
                "address_line2": address.address_line2,
                "city": address.city,
                "province": address.province,
                "postal_code": address.postal_code,
                "country": address.country,
            }
        }}
    )
    return {"success": True, "message": "Address updated successfully"}


@router.put("/users/me/preferences")
async def update_user_preferences(request: Request):
    """Update user preferences"""
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = _get_db()
    data = await request.json()
    allowed_fields = ["permissions_asked", "support_onboarded", "notification_settings"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if update_data:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {f"preferences.{k}": v for k, v in update_data.items()}}
        )
    return {"success": True, "preferences": update_data}


@router.get("/users/me/preferences")
async def get_user_preferences(request: Request):
    """Get user preferences"""
    user = await _get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"preferences": user.get("preferences", {})}


# ═══════════════════════════
# PASSWORD RESET
# ═══════════════════════════

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


def _create_reset_token(email: str) -> str:
    payload = {
        "email": email,
        "type": "password_reset",
        # Bug-fix #156 (R18): jti so the token can be one-shot invalidated
        # after successful reset (prevents replay).
        "jti": uuid.uuid4().hex,
        "exp": datetime.now(timezone.utc).timestamp() + 3600,
    }
    return jwt.encode(payload, _jwt_secret, algorithm=_jwt_algorithm)


def _verify_reset_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("email")
    except Exception:
        return None


def _decode_reset_payload(token: str) -> Optional[dict]:
    """Like _verify_reset_token but returns the full payload (for jti)."""
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        if payload.get("type") != "password_reset":
            return None
        return payload
    except Exception:
        return None


async def _is_reset_token_consumed(jti: str) -> bool:
    db = _get_db()
    if not db or not jti:
        return False
    try:
        doc = await db.password_reset_used.find_one({"jti": jti}, {"_id": 0, "jti": 1})
        return bool(doc)
    except Exception:
        return False


async def _consume_reset_token(jti: str, email: str) -> None:
    db = _get_db()
    if not db or not jti:
        return
    try:
        await db.password_reset_used.insert_one({
            "jti": jti,
            "email": email,
            "used_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            await db.password_reset_used.create_index("used_at", expireAfterSeconds=7200)
        except Exception:
            pass
    except Exception as e:
        logging.warning(f"[RESET] consume jti failed: {e}")


@router.post("/auth/forgot-password")
async def forgot_password(request_data: PasswordResetRequest, request: Request):
    """Request a password reset email"""
    db = _get_db()
    email = request_data.email.lower().strip()

    user = await db.users.find_one({"email": email}, {"_id": 0})
    team_member = await db.team_members.find_one({"email": email}, {"_id": 0})

    if not user and not team_member:
        return {
            "message": "If an account exists with this email, you will receive a password reset link.",
            "success": False,
        }

    reset_token = _create_reset_token(email)

    name = "there"
    if user:
        name = user.get("name") or user.get("first_name") or "there"
    elif team_member:
        name = team_member.get("name") or team_member.get("first_name") or "there"

    origin = request.headers.get("origin", "")
    if not origin or origin == "null":
        origin = request.headers.get("referer", "").rstrip("/")
        if not origin:
            origin = ""
    reset_link = f"{origin}/reset-password?token={reset_token}"

    email_sent = False
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

    if RESEND_API_KEY:
        try:
            import resend
            resend.api_key = RESEND_API_KEY
            # iter 282g — tenant-aware branding: AUREM hosts get the new
            # branded template; other tenants (ReRoots etc.) keep their
            # existing branding.
            is_aurem = "aurem" in (origin or "").lower()
            if is_aurem:
                try:
                    from services.brand_emails import render_password_reset
                    html_content = render_password_reset(reset_url=reset_link)
                    from_addr = os.environ.get(
                        "RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>"
                    )
                    subject = "Reset your AUREM password"
                except Exception as _render_err:
                    logging.warning(f"[reset] branded render failed: {_render_err}")
                    is_aurem = False
            if not is_aurem:
                html_content = f"""
                <div style="background:#060608;color:#F0EBE0;padding:40px;font-family:Georgia,serif;">
                    <h2 style="color:#C9A86E;margin-bottom:20px;">Password Reset</h2>
                    <p style="margin-bottom:16px;">Hi {name},</p>
                    <p style="margin-bottom:24px;">Click below to reset your password. Link expires in 1 hour.</p>
                    <a href="{reset_link}"
                       style="background:#C9A86E;color:#060608;padding:14px 28px;
                              text-decoration:none;border-radius:4px;display:inline-block;
                              font-family:sans-serif;letter-spacing:0.1em;font-size:12px;">
                        RESET PASSWORD
                    </a>
                    <p style="color:#5C5548;font-size:12px;margin-top:24px;">
                        If you didn't request this, ignore this email.
                    </p>
                </div>
                """
                from_addr = "ReRoots <hello@reroots.ca>"
                subject = "Reset your ReRoots password"
            params = {
                "from": from_addr,
                "to": [email],
                "subject": subject,
                "html": html_content,
            }
            result = await asyncio.to_thread(resend.Emails.send, params)
            if result and hasattr(result, "id") and result.id:
                logging.info(f"Password reset email sent to: {email}, ID: {result.id}")
                email_sent = True
            else:
                email_sent = False
        except Exception as e:
            logging.error(f"Failed to send password reset email: {e}")
            email_sent = False

    logging.info(f"Returning reset link directly: {reset_link}")
    return {
        "message": "If this email exists, you will receive reset instructions.",
        "success": True,
        "reset_link": reset_link,
        "email_sent": email_sent,
    }


@router.post("/auth/reset-password")
async def reset_password(request_data: PasswordResetConfirm):
    """Reset password using the token from email"""
    db = _get_db()
    # Bug-fix #156 (R18): one-shot reset tokens.
    rp = _decode_reset_payload(request_data.token)
    if not rp:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    email = rp.get("email")
    jti = rp.get("jti")
    if jti and await _is_reset_token_consumed(jti):
        raise HTTPException(status_code=400, detail="Reset token already used")

    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    try:
        from services.email_templates import validate_password_strength
        is_valid, message = validate_password_strength(request_data.new_password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
    except ImportError:
        pass

    hashed_password = bcrypt.hashpw(request_data.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Sync BOTH `password` and `password_hash` so admin/customer login flows
    # (which read different fields) stay in lockstep across users / aurem_users
    # / platform_users / team_members collections.
    user_result = await db.users.update_one(
        {"email": email},
        {"$set": {"password": hashed_password, "password_hash": hashed_password}},
    )
    team_result = await db.team_members.update_one(
        {"email": email}, {"$set": {"password_hash": hashed_password}}
    )
    try:
        await db.aurem_users.update_one(
            {"email": email}, {"$set": {"password_hash": hashed_password}}
        )
        await db.platform_users.update_one(
            {"email": email}, {"$set": {"password_hash": hashed_password}}
        )
    except Exception as _e:
        logging.warning(f"[RESET] secondary mirror failed: {_e}")

    if user_result.modified_count == 0 and team_result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    # Bug-fix #156 (R18): mark this reset jti as consumed so the same
    # link can't be replayed within its 1-hour validity window.
    if jti:
        await _consume_reset_token(jti, email)

    logging.info(f"Password reset successful for: {email}")
    return {"message": "Password reset successful. You can now log in with your new password."}


@router.get("/auth/verify-reset-token")
async def verify_token(token: str):
    """Verify if a reset token is valid.

    Bug-fix #156 (R18): do NOT leak the email back to the caller — that
    let an attacker brute-force-enumerate emails from leaked tokens.
    Only return a boolean validity flag.
    """
    rp = _decode_reset_payload(token)
    if not rp:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if rp.get("jti") and await _is_reset_token_consumed(rp["jti"]):
        raise HTTPException(status_code=400, detail="Reset token already used")
    return {"valid": True}


# ═══════════════════════════
# PHONE LOGIN
# ═══════════════════════════

@router.post("/auth/phone-login")
async def phone_login(data: dict):
    """Login or register with phone number using SMS verification"""
    db = _get_db()
    phone = data.get("phone")
    code = data.get("code")

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    if not code:
        try:
            from services.sms_service import send_sms_verification
            result = await send_sms_verification(phone)
        except ImportError:
            result = {"success": False, "error": "SMS service not configured"}
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to send SMS"))
        return {"message": "Verification code sent", "awaiting_code": True}

    try:
        from services.sms_service import verify_sms_code
        verify_result = await verify_sms_code(phone, code)
    except ImportError:
        verify_result = {"success": False, "error": "SMS service not configured"}
    if not verify_result.get("success"):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    formatted_phone = phone if phone.startswith("+") else f"+1{phone}"
    user = await db.users.find_one({"phone": formatted_phone}, {"_id": 0})

    if not user:
        user = {
            "id": str(uuid.uuid4()),
            "email": None,
            "first_name": "User",
            "last_name": formatted_phone[-4:],
            "phone": formatted_phone,
            "phone_verified": True,
            "role": "customer",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        user.pop("_id", None)
    else:
        await db.users.update_one(
            {"id": user["id"]}, {"$set": {"phone_verified": True}}
        )

    token_payload = {
        "user_id": user["id"],
        "email": user.get("email"),
        "phone": formatted_phone,
        "role": user.get("role", "customer"),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = jwt.encode(token_payload, _jwt_secret, algorithm=_jwt_algorithm)

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "phone": formatted_phone,
            "role": user.get("role", "customer"),
        },
    }


@router.post("/auth/password-reset-sms")
async def password_reset_via_sms(data: dict):
    """Reset password using SMS verification"""
    db = _get_db()
    phone = data.get("phone")
    code = data.get("code")
    new_password = data.get("new_password")

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    formatted_phone = phone if phone.startswith("+") else f"+1{phone}"

    if not code:
        user = await db.users.find_one({"phone": formatted_phone})
        if not user:
            raise HTTPException(status_code=404, detail="No account found with this phone number")

        try:
            from services.sms_service import send_sms_verification
            result = await send_sms_verification(phone)
        except ImportError:
            result = {"success": False, "error": "SMS service not configured"}
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to send SMS"))
        return {"message": "Verification code sent", "awaiting_code": True}

    if not new_password:
        raise HTTPException(status_code=400, detail="New password required")

    try:
        from services.sms_service import verify_sms_code
        verify_result = await verify_sms_code(phone, code)
    except ImportError:
        verify_result = {"success": False, "error": "SMS service not configured"}
    if not verify_result.get("success"):
        raise HTTPException(status_code=400, detail="Invalid verification code")

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())
    result = await db.users.update_one(
        {"phone": formatted_phone}, {"$set": {"password_hash": hashed.decode("utf-8")}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "Password reset successful"}


# ═══════════════════════════
# PRODUCT CRUD (Admin)
# ═══════════════════════════

@router.put("/products/{product_id}")
async def update_product(product_id: str, product_data: dict, request: Request):
    """Update a single product with STRICT ID scoping"""
    await _require_admin(request)
    db = _get_db()

    if not product_id or not isinstance(product_id, str):
        raise HTTPException(status_code=400, detail="Valid product_id required")

    existing = await db.products.find_one({"id": product_id})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    prev_stock = existing.get("stock", 0) or existing.get("quantity", 0) or 0

    update_data = {k: v for k, v in product_data.items() if k != "_id"}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.products.update_one({"id": product_id}, {"$set": update_data})

    if result.modified_count == 0 and result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found or no changes made")

    updated = await db.products.find_one({"id": product_id}, {"_id": 0})

    new_stock = update_data.get("stock", 0) or update_data.get("quantity", 0) or 0
    # NOTE: Restock notification trigger removed (storefront feature deprecated, iter 322h).

    reorder_point = updated.get("reorder_point", 10) if updated else 10
    if new_stock <= reorder_point and new_stock > 0:
        try:
            from routers.email_service import send_low_stock_alert
            send_low_stock_alert(
                product_name=updated.get("name", "Unknown Product"),
                sku=updated.get("sku", product_id),
                current_stock=new_stock,
                reorder_point=reorder_point
            )
        except Exception:
            pass

    try:
        from server import invalidate_cache
        invalidate_cache()
    except Exception:
        pass

    if _ws_manager:
        await _ws_manager.broadcast_to_all({
            "type": "product_sync",
            "action": "updated",
            "product_id": product_id,
            "product_name": updated.get("name") if updated else None
        })

    return updated


@router.delete("/products/{product_id}")
async def delete_product(product_id: str, request: Request):
    await _require_admin(request)
    db = _get_db()

    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    product_name = product.get("name") if product else None

    await db.products.delete_one({"id": product_id})

    try:
        from server import invalidate_cache
        invalidate_cache()
    except Exception:
        pass

    if _ws_manager:
        await _ws_manager.broadcast_to_all({
            "type": "product_sync",
            "action": "deleted",
            "product_id": product_id,
            "product_name": product_name
        })

    return {"message": "Product deleted"}


# ═══════════════════════════
# ADMIN AI ASSISTANT
# ═══════════════════════════

@router.post("/admin/ai-assistant")
async def admin_ai_assistant(data: dict, request: Request):
    """AI Assistant for admin help"""
    await _require_admin(request)

    from middleware.security import sanitize_input
    message = sanitize_input(data.get("message", ""))
    context = data.get("context", "admin_help")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            llm_key = os.environ.get("CLAUDE_API_KEY", "")

        chat = LlmChat(
            api_key=llm_key,
            session_id="admin-assistant",
            system_message="""You are a helpful AI assistant for ReRoots skincare e-commerce store administrators.
You help with: Managing products, inventory, orders, payments, settings, troubleshooting.
Be concise, helpful, and friendly.""",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        user_message = UserMessage(text=message)
        response = await chat.send_message(user_message)

        return {"response": response.strip()}
    except Exception as e:
        logging.error(f"AI Assistant error: {e}")
        return {"response": "I'm having trouble connecting right now. Please try again."}


# ═══════════════════════════
# WHATSAPP VALIDATE
# ═══════════════════════════

@router.post("/whatsapp/validate-number")
async def validate_whatsapp_number_endpoint(data: dict = Body(...)):
    """Public endpoint to validate a WhatsApp number."""
    phone = data.get("phone")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    try:
        from services.twilio_service import validate_whatsapp_number
        result = await validate_whatsapp_number(phone)
        return result
    except ImportError:
        return {"valid": False, "error": "WhatsApp validation not configured"}
