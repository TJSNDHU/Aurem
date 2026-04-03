"""
ReRoots AI PWA Backend Router
Handles Push Notifications, Voice Synthesis, and AI Chat
"""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import httpx
from datetime import datetime

router = APIRouter(prefix="/api/pwa", tags=["PWA"])

# Environment variables
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:support@reroots.ca")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
VOXTRAL_API_KEY = os.environ.get("VOXTRAL_API_KEY", "")  # Optional Voxtral key


# ========== Pydantic Models ==========

class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {p256dh: str, auth: str}
    user_id: Optional[str] = None


class PushNotification(BaseModel):
    title: str
    body: str
    icon: Optional[str] = "/icons/icon-192x192.png"
    badge: Optional[str] = "/icons/icon-96x96.png"
    tag: Optional[str] = "reroots-notification"
    url: Optional[str] = "/pwa"
    require_interaction: Optional[bool] = False


class VoiceSynthesisRequest(BaseModel):
    text: str
    voice_id: Optional[str] = "reroots-consultant"
    model: Optional[str] = "voxtral-v1"
    streaming: Optional[bool] = True


class AIChatRequest(BaseModel):
    message: str
    context: Optional[str] = "skincare_consultant"
    conversation_history: Optional[List[dict]] = []


# ========== Push Notification Endpoints ==========

@router.get("/vapid-key")
async def get_vapid_key():
    """Get VAPID public key for client-side push subscription"""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="VAPID key not configured")
    
    return {"publicKey": VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe_push(subscription: PushSubscription, request: Request):
    """Subscribe to push notifications"""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Store subscription
        sub_data = {
            "endpoint": subscription.endpoint,
            "keys": subscription.keys,
            "user_id": subscription.user_id,
            "created_at": datetime.utcnow(),
            "user_agent": request.headers.get("user-agent", ""),
            "active": True
        }
        
        # Upsert by endpoint
        db.push_subscriptions.update_one(
            {"endpoint": subscription.endpoint},
            {"$set": sub_data},
            upsert=True
        )
        
        return {"success": True, "message": "Subscribed to push notifications"}
        
    except Exception as e:
        print(f"[PWA] Subscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_push(subscription: PushSubscription):
    """Unsubscribe from push notifications"""
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        db.push_subscriptions.update_one(
            {"endpoint": subscription.endpoint},
            {"$set": {"active": False}}
        )
        
        return {"success": True, "message": "Unsubscribed from push notifications"}
        
    except Exception as e:
        print(f"[PWA] Unsubscribe error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-notification")
async def send_push_notification(
    notification: PushNotification,
    user_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """Send push notification to subscribed users"""
    try:
        from pywebpush import webpush, WebPushException
        from pymongo import MongoClient
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Get subscriptions
        query = {"active": True}
        if user_id:
            query["user_id"] = user_id
            
        subscriptions = list(db.push_subscriptions.find(query))
        
        if not subscriptions:
            return {"success": False, "message": "No active subscriptions found"}
        
        # Prepare payload
        payload = json.dumps({
            "title": notification.title,
            "body": notification.body,
            "icon": notification.icon,
            "badge": notification.badge,
            "tag": notification.tag,
            "data": {"url": notification.url},
            "requireInteraction": notification.require_interaction
        })
        
        sent_count = 0
        failed_endpoints = []
        
        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub["endpoint"],
                        "keys": sub["keys"]
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": VAPID_SUBJECT
                    }
                )
                sent_count += 1
            except WebPushException as e:
                print(f"[PWA] Push failed for {sub['endpoint']}: {e}")
                failed_endpoints.append(sub["endpoint"])
                
                # Mark invalid subscriptions
                if e.response and e.response.status_code in [404, 410]:
                    db.push_subscriptions.update_one(
                        {"endpoint": sub["endpoint"]},
                        {"$set": {"active": False}}
                    )
        
        return {
            "success": True,
            "sent": sent_count,
            "failed": len(failed_endpoints),
            "message": f"Sent to {sent_count} devices"
        }
        
    except ImportError:
        raise HTTPException(status_code=500, detail="pywebpush not installed")
    except Exception as e:
        print(f"[PWA] Send notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Voice Synthesis Endpoints ==========

@router.get("/voice/config")
async def get_voice_config():
    """Get voice configuration (Voxtral availability)"""
    return {
        "voxtral_available": bool(VOXTRAL_API_KEY),
        "voxtral_key": VOXTRAL_API_KEY if VOXTRAL_API_KEY else None,
        "fallback": "web_speech_api"
    }


@router.post("/voice/synthesize")
async def synthesize_voice(request: VoiceSynthesisRequest):
    """
    Synthesize speech using Voxtral TTS
    Falls back to error if Voxtral unavailable (client uses Web Speech API)
    """
    if not VOXTRAL_API_KEY:
        raise HTTPException(
            status_code=503, 
            detail="Voxtral TTS not configured. Use Web Speech API fallback."
        )
    
    try:
        # Voxtral API call (Mistral AI Studio)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.mistral.ai/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {VOXTRAL_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": request.model,
                    "input": request.text,
                    "voice": request.voice_id,
                    "response_format": "mp3"
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Voxtral TTS failed")
            
            # Return audio bytes
            from fastapi.responses import Response
            return Response(
                content=response.content,
                media_type="audio/mpeg"
            )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Voxtral TTS timeout")
    except Exception as e:
        print(f"[PWA] Voice synthesis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== AI Chat Endpoints ==========

@router.post("/ai/chat")
async def ai_chat(request: AIChatRequest):
    """AI skincare consultant chat endpoint"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    try:
        from emergentintegrations.llm import LlmChat, ChatMessage
        
        # Build system prompt for skincare consultant
        system_prompt = """You are an expert skincare consultant for ReRoots, a luxury biotech skincare brand. 
Your role is to:
- Provide personalized skincare advice
- Explain product ingredients and their benefits (especially PDRN, peptides, antioxidants)
- Help users build effective skincare routines
- Answer questions about skin concerns (acne, aging, hyperpigmentation, sensitivity)
- Recommend products from the ReRoots AURA-GEN line when appropriate

Keep responses concise (2-3 sentences for voice), warm, and professional.
Use simple language that's easy to understand.
If asked about medical conditions, recommend consulting a dermatologist."""

        # Build conversation
        messages = [ChatMessage(role="system", content=system_prompt)]
        
        # Add conversation history
        for msg in request.conversation_history[-5:]:  # Last 5 messages for context
            messages.append(ChatMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", "")
            ))
        
        # Add current message
        messages.append(ChatMessage(role="user", content=request.message))
        
        # Get AI response
        llm = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            model="claude-sonnet-4-20250514"  # Using Claude Sonnet for quality responses
        )
        
        response = await llm.chat_async(messages=messages)
        
        return {
            "success": True,
            "response": response,
            "context": request.context
        }
        
    except ImportError:
        # Fallback to basic response if emergentintegrations not available
        return {
            "success": True,
            "response": "I apologize, but I'm having trouble connecting to the AI service. Please try again in a moment.",
            "context": request.context
        }
    except Exception as e:
        print(f"[PWA] AI chat error: {e}")
        return {
            "success": False,
            "response": "I apologize, I encountered an error. Please try rephrasing your question.",
            "error": str(e)
        }


# ========== Cart Recovery Endpoints ==========

@router.post("/cart-recovery/trigger")
async def trigger_cart_recovery(user_id: str, background_tasks: BackgroundTasks):
    """Trigger cart recovery push notification for abandoned cart"""
    try:
        from pymongo import MongoClient
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Get user's cart
        cart = db.carts.find_one({"user_id": user_id})
        
        if not cart or not cart.get("items"):
            return {"success": False, "message": "No cart found"}
        
        # Send recovery notification
        notification = PushNotification(
            title="Your skin is waiting! 💫",
            body=f"You have {len(cart['items'])} item(s) in your cart. Complete your order for radiant skin!",
            url="/pwa?tab=shop",
            tag="cart-recovery",
            require_interaction=True
        )
        
        await send_push_notification(notification, user_id=user_id)
        
        # Log recovery attempt
        db.cart_recovery_logs.insert_one({
            "user_id": user_id,
            "cart_items": len(cart["items"]),
            "triggered_at": datetime.utcnow()
        })
        
        return {"success": True, "message": "Cart recovery notification sent"}
        
    except Exception as e:
        print(f"[PWA] Cart recovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Test Endpoint ==========

@router.get("/test")
async def test_pwa():
    """Test PWA router is working"""
    return {
        "status": "ok",
        "message": "ReRoots AI PWA Backend Active",
        "vapid_configured": bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY),
        "voxtral_configured": bool(VOXTRAL_API_KEY),
        "ai_configured": bool(EMERGENT_LLM_KEY),
        "timestamp": datetime.utcnow().isoformat()
    }


# ========== Admin Analytics Endpoints (Single Admin Policy) ==========

@router.get("/admin/analytics")
async def get_pwa_analytics():
    """Get PWA analytics for Master Admin dashboard"""
    try:
        from pymongo import MongoClient
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Get biometric registration stats
        biometric_registrations = list(db.biometric_logs.find({
            "event_type": "registration"
        }).sort("timestamp", -1).limit(100))
        
        biometric_logins = list(db.biometric_logs.find({
            "event_type": "login"
        }).sort("timestamp", -1).limit(100))
        
        success_logins = len([log for log in biometric_logins if log.get("success")])
        failed_logins = len([log for log in biometric_logins if not log.get("success")])
        
        # Get PWA-specific abandoned carts
        pwa_carts = list(db.carts.find({
            "source": "pwa",
            "status": {"$ne": "converted"},
            "items": {"$exists": True, "$ne": []}
        }).sort("updated_at", -1).limit(50))
        
        # Get push notification stats
        push_subs = db.push_subscriptions.count_documents({"active": True})
        push_sent = db.push_logs.count_documents({}) if "push_logs" in db.list_collection_names() else 0
        
        # Get vault usage stats (photo counts by user)
        vault_stats = {
            "total_vaults": db.vault_metadata.count_documents({}) if "vault_metadata" in db.list_collection_names() else 0,
            "active_users": db.vault_metadata.count_documents({"photo_count": {"$gt": 0}}) if "vault_metadata" in db.list_collection_names() else 0
        }
        
        # Get PWA session stats
        pwa_sessions = db.sessions.count_documents({
            "source": "pwa"
        }) if "sessions" in db.list_collection_names() else 0
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "biometric": {
                "total_registrations": len(biometric_registrations),
                "login_success_rate": round(success_logins / max(success_logins + failed_logins, 1) * 100, 1),
                "success_logins": success_logins,
                "failed_logins": failed_logins,
                "recent_registrations": [
                    {
                        "user_id": str(r.get("user_id", "")),
                        "method": r.get("method", "webauthn"),
                        "timestamp": r.get("timestamp", "").isoformat() if hasattr(r.get("timestamp", ""), "isoformat") else str(r.get("timestamp", ""))
                    }
                    for r in biometric_registrations[:10]
                ]
            },
            "abandoned_carts": {
                "pwa_count": len(pwa_carts),
                "total_value": sum(
                    sum(item.get("price", 0) * item.get("quantity", 1) for item in cart.get("items", []))
                    for cart in pwa_carts
                ),
                "carts": [
                    {
                        "session_id": cart.get("session_id", ""),
                        "items_count": len(cart.get("items", [])),
                        "total": sum(item.get("price", 0) * item.get("quantity", 1) for item in cart.get("items", [])),
                        "updated_at": cart.get("updated_at", "").isoformat() if hasattr(cart.get("updated_at", ""), "isoformat") else str(cart.get("updated_at", ""))
                    }
                    for cart in pwa_carts[:10]
                ]
            },
            "push_notifications": {
                "active_subscriptions": push_subs,
                "total_sent": push_sent
            },
            "vault": vault_stats,
            "sessions": {
                "pwa_sessions": pwa_sessions
            }
        }
        
    except Exception as e:
        print(f"[PWA Admin] Analytics error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.post("/admin/log-biometric")
async def log_biometric_event(request: Request):
    """Log biometric authentication events for admin analytics"""
    try:
        from pymongo import MongoClient
        
        data = await request.json()
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        log_entry = {
            "event_type": data.get("event_type", "unknown"),  # registration, login, pin_fallback
            "user_id": data.get("user_id"),
            "method": data.get("method", "webauthn"),  # webauthn, pin
            "success": data.get("success", True),
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": datetime.utcnow()
        }
        
        db.biometric_logs.insert_one(log_entry)
        
        return {"success": True, "logged": True}
        
    except Exception as e:
        print(f"[PWA Admin] Log biometric error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/admin/log-vault-activity")
async def log_vault_activity(request: Request):
    """Log vault activity for admin analytics"""
    try:
        from pymongo import MongoClient
        
        data = await request.json()
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url)
        db = client[db_name]
        
        # Update or create vault metadata
        db.vault_metadata.update_one(
            {"user_id": data.get("user_id")},
            {
                "$set": {
                    "user_id": data.get("user_id"),
                    "photo_count": data.get("photo_count", 0),
                    "storage_used": data.get("storage_used", 0),
                    "last_activity": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return {"success": True}
        
    except Exception as e:
        print(f"[PWA Admin] Log vault activity error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/health")
async def pwa_health_check():
    """Health check for PWA-to-Admin connection (Circuit Breaker monitoring)"""
    try:
        from pymongo import MongoClient
        from utils.encryption import is_encryption_available
        
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        
        # Test DB connection
        db.command("ping")
        
        # Check encryption status
        encryption_status = "AES-256 Active" if is_encryption_available() else "Passthrough (Not Configured)"
        
        return {
            "status": "healthy",
            "database": "connected",
            "vapid": "configured" if VAPID_PUBLIC_KEY else "missing",
            "ai": "configured" if EMERGENT_LLM_KEY else "missing",
            "encryption": encryption_status,
            "service_worker": "v9",
            "vault_security": "AES-256-GCM" if is_encryption_available() else "Client-Side Only",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/admin/system-status")
async def get_system_status():
    """Get detailed PWA system status including version and encryption"""
    try:
        from utils.encryption import is_encryption_available
        
        encryption_active = is_encryption_available()
        
        return {
            "success": True,
            "pwa_version": "v2.0.0-Biotech Fortress",
            "service_worker_version": "v9",
            "cache_version": "reroots-pwa-v9-fortress",
            "security": {
                "vault_encryption": "AES-256-GCM Active" if encryption_active else "Passthrough Mode",
                "encryption_key_configured": encryption_active,
                "biometric_gate": "WebAuthn + PIN Fallback",
                "key_derivation": "PBKDF2 (100,000 iterations)"
            },
            "features": {
                "push_notifications": bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY),
                "ai_consultant": bool(EMERGENT_LLM_KEY),
                "voxtral_tts": bool(VOXTRAL_API_KEY),
                "live_sync": True,
                "offline_mode": True
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
