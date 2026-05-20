"""
AUREM AI SMS Alerts Router
Twilio-powered SMS notifications, OTP, and alerts
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from utils.require_auth import require_admin
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

# Bug-fix 118 — /send /send-otp /bulk-send were unauthenticated, allowing
# attackers to spam any phone via Twilio + harvest OTPs. Admin-gated.
router = APIRouter(
    prefix="/api/sms",
    tags=["sms-alerts"],
    dependencies=[Depends(require_admin)],
)

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database

# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SendSMSRequest(BaseModel):
    phone_number: str  # E.164 format: +14155551234
    message: str
    template: Optional[str] = None  # order_confirmation, shipping, otp, promo

class SendOTPRequest(BaseModel):
    phone_number: str

class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str

class BulkSMSRequest(BaseModel):
    phone_numbers: List[str]
    message: str
    template: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# SMS TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

SMS_TEMPLATES = {
    "order_confirmation": "AUREM: Your order #{order_id} is confirmed! Total: ${total}. Track at aurem.live/track",
    "shipping": "AUREM: Great news! Your order #{order_id} has shipped. Tracking: {tracking_number}",
    "delivery": "AUREM: Your AUREM order has been delivered! Enjoy your skincare journey.",
    "otp": "AUREM: Your verification code is {code}. Valid for 10 minutes.",
    "welcome": "Welcome to AUREM! Your skin transformation journey begins now. Shop at aurem.live",
    "promo": "AUREM: {promo_message} Use code: {code}. Valid until {expiry}. aurem.live",
    "restock": "AUREM: {product_name} is back in stock! Get yours before it sells out: aurem.live/shop",
    "abandoned_cart": "AUREM: You left items in your cart! Complete your order now: aurem.live/cart",
    "review_request": "AUREM: How's your {product_name}? Share your review: {review_link}",
    "birthday": "AUREM: Happy Birthday! Here's {discount}% off your next order. Code: {code}"
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_twilio_client():
    """Get Twilio client with credentials"""
    try:
        from twilio.rest import Client
        
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            return None
        
        return Client(account_sid, auth_token)
    except Exception as e:
        print(f"Twilio client error: {e}")
        return None

def format_phone_number(phone: str) -> str:
    """Ensure phone number is in E.164 format"""
    # Remove all non-digit characters except +
    cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
    
    # Add + if missing
    if not cleaned.startswith('+'):
        # Assume US/Canada if 10 digits
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    return cleaned


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/send")
async def send_sms(data: SendSMSRequest):
    """Send a single SMS message.

    KILL SWITCH (A2P 10DLC pending): SMS sends are suppressed and rerouted to
    WhatsApp. Skip is logged to MongoDB `sms_skipped_logs`.
    """
    from services.sms_killswitch import is_sms_disabled, log_skipped_sms

    to_number = format_phone_number(data.phone_number)

    if is_sms_disabled():
        # Reroute to WhatsApp so customer still gets the message
        try:
            from shared.providers.twilio import send_whatsapp_message
            wa_result = await send_whatsapp_message(to_number, data.message)
        except Exception as e:
            wa_result = {"success": False, "error": f"whatsapp_fallback_failed: {e}"}

        await log_skipped_sms(
            to=to_number,
            message=data.message,
            caller="routers.sms_alerts_router.send_sms",
            redirected_to="whatsapp" if wa_result.get("success") else None,
        )
        try:
            await db.sms_logs.insert_one({
                "to": to_number,
                "message": data.message,
                "template": data.template,
                "status": "skipped_a2p_pending",
                "redirected_to": "whatsapp" if wa_result.get("success") else None,
                "sent_at": datetime.now(timezone.utc),
            })
        except Exception:
            pass
        return {
            "success": bool(wa_result.get("success")),
            "sms_skipped": True,
            "skip_reason": "A2P_10DLC_pending",
            "redirected_to": "whatsapp",
            "whatsapp_result": wa_result,
        }

    client = get_twilio_client()
    if not client:
        raise HTTPException(status_code=500, detail="SMS service not configured")
    
    try:
        from_number = os.environ.get("TWILIO_PHONE_NUMBER")
        if not from_number:
            raise HTTPException(status_code=500, detail="Twilio phone number not configured")
        
        # Send message
        message = client.messages.create(
            body=data.message,
            from_=from_number,
            to=to_number
        )
        
        # Log message
        await db.sms_logs.insert_one({
            "message_sid": message.sid,
            "to": to_number,
            "message": data.message,
            "template": data.template,
            "status": message.status,
            "sent_at": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "message_sid": message.sid,
            "status": message.status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")


@router.post("/send-otp")
async def send_otp(data: SendOTPRequest):
    """Send OTP verification code.

    KILL SWITCH: when SMS is disabled (A2P pending), the OTP is delivered via
    WhatsApp using a 6-digit numeric code generated locally. Verification then
    runs against this stored hash. Twilio Verify (which uses an unregistered
    number under the hood) is bypassed entirely.
    """
    from services.sms_killswitch import is_sms_disabled, log_skipped_sms
    import hashlib
    import secrets

    to_number = format_phone_number(data.phone_number)

    if is_sms_disabled():
        code = f"{secrets.randbelow(1_000_000):06d}"
        otp_message = f"AUREM: Your verification code is {code}. Valid for 10 minutes."
        try:
            from shared.providers.twilio import send_whatsapp_message
            wa_result = await send_whatsapp_message(to_number, otp_message)
        except Exception as e:
            wa_result = {"success": False, "error": f"whatsapp_fallback_failed: {e}"}

        # Persist hashed OTP for verification
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        try:
            await db.otp_logs.insert_one({
                "phone": to_number,
                "code_hash": code_hash,
                "channel": "whatsapp",
                "status": "sent" if wa_result.get("success") else "failed",
                "sent_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "verified": False,
                "sms_skipped": True,
            })
        except Exception:
            pass

        await log_skipped_sms(
            to=to_number,
            message="[OTP]",
            caller="routers.sms_alerts_router.send_otp",
            redirected_to="whatsapp" if wa_result.get("success") else None,
        )

        return {
            "success": bool(wa_result.get("success")),
            "status": "delivered_via_whatsapp" if wa_result.get("success") else "failed",
            "channel": "whatsapp",
            "sms_skipped": True,
            "skip_reason": "A2P_10DLC_pending",
            "message": "OTP sent via WhatsApp (SMS suppressed pending A2P 10DLC approval)",
        }

    client = get_twilio_client()
    if not client:
        raise HTTPException(status_code=500, detail="SMS service not configured")

    try:
        verify_service_sid = os.environ.get("TWILIO_VERIFY_SERVICE")
        if not verify_service_sid:
            raise HTTPException(status_code=500, detail="Twilio Verify service not configured")
        
        # Send verification
        verification = client.verify.v2.services(verify_service_sid).verifications.create(
            to=to_number,
            channel="sms"
        )
        
        # Log attempt
        await db.otp_logs.insert_one({
            "phone": to_number,
            "status": verification.status,
            "sent_at": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "status": verification.status,
            "message": "OTP sent successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")


@router.post("/verify-otp")
async def verify_otp(data: VerifyOTPRequest):
    """Verify OTP code.

    KILL SWITCH: if the most recent OTP for this phone was delivered via
    WhatsApp (sms_skipped=True), verify against our local hash instead of
    Twilio Verify.
    """
    from services.sms_killswitch import is_sms_disabled
    import hashlib

    to_number = format_phone_number(data.phone_number)

    # Look up the most recent OTP record for this phone
    try:
        latest = await db.otp_logs.find_one(
            {"phone": to_number},
            {"_id": 0},
            sort=[("sent_at", -1)],
        )
    except Exception:
        latest = None

    if is_sms_disabled() or (latest and latest.get("sms_skipped")):
        if not latest or not latest.get("code_hash"):
            return {"valid": False, "status": "no_pending_otp"}
        if latest.get("verified"):
            return {"valid": False, "status": "already_used"}
        code_hash = hashlib.sha256(data.code.encode()).hexdigest()
        is_valid = code_hash == latest["code_hash"]
        if is_valid:
            await db.otp_logs.update_one(
                {"phone": to_number, "code_hash": latest["code_hash"], "verified": False},
                {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc)}},
            )
        return {"valid": is_valid, "status": "approved" if is_valid else "rejected"}

    client = get_twilio_client()
    if not client:
        raise HTTPException(status_code=500, detail="SMS service not configured")
    
    try:
        verify_service_sid = os.environ.get("TWILIO_VERIFY_SERVICE")
        if not verify_service_sid:
            raise HTTPException(status_code=500, detail="Twilio Verify service not configured")
        
        # Verify code
        check = client.verify.v2.services(verify_service_sid).verification_checks.create(
            to=to_number,
            code=data.code
        )
        
        is_valid = check.status == "approved"
        
        # Update log
        if is_valid:
            await db.otp_logs.update_one(
                {"phone": to_number, "verified": {"$ne": True}},
                {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc)}}
            )
        
        return {
            "valid": is_valid,
            "status": check.status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/send-templated")
async def send_templated_sms(
    phone_number: str,
    template: str,
    variables: Dict[str, str]
):
    """Send SMS using a predefined template"""
    if template not in SMS_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown template: {template}")
    
    # Format message with variables
    message = SMS_TEMPLATES[template]
    try:
        for key, value in variables.items():
            message = message.replace(f"{{{key}}}", str(value))
    except Exception:
        pass
    
    # Send using main function
    return await send_sms(SendSMSRequest(
        phone_number=phone_number,
        message=message,
        template=template
    ))


@router.post("/bulk-send")
async def send_bulk_sms(data: BulkSMSRequest):
    """Send SMS to multiple recipients"""
    results = []
    
    for phone in data.phone_numbers:
        try:
            result = await send_sms(SendSMSRequest(
                phone_number=phone,
                message=data.message,
                template=data.template
            ))
            results.append({"phone": phone, "success": True, "message_sid": result.get("message_sid")})
        except Exception as e:
            results.append({"phone": phone, "success": False, "error": str(e)})
    
    success_count = sum(1 for r in results if r["success"])
    
    return {
        "total": len(data.phone_numbers),
        "success": success_count,
        "failed": len(data.phone_numbers) - success_count,
        "results": results
    }


@router.get("/templates")
async def get_sms_templates():
    """Get all available SMS templates"""
    return {"templates": SMS_TEMPLATES}


@router.get("/logs")
async def get_sms_logs(limit: int = 50, skip: int = 0):
    """Get SMS sending history"""
    logs = await db.sms_logs.find(
        {},
        {"_id": 0}
    ).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.sms_logs.count_documents({})
    
    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "skip": skip
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATED ALERTS (Called by other services)
# ═══════════════════════════════════════════════════════════════════════════════

async def send_order_confirmation_sms(phone: str, order_id: str, total: float) -> bool:
    """Send order confirmation SMS"""
    try:
        await send_templated_sms(
            phone_number=phone,
            template="order_confirmation",
            variables={"order_id": order_id, "total": f"{total:.2f}"}
        )
        return True
    except:
        return False

async def send_shipping_notification_sms(phone: str, order_id: str, tracking_number: str) -> bool:
    """Send shipping notification SMS"""
    try:
        await send_templated_sms(
            phone_number=phone,
            template="shipping",
            variables={"order_id": order_id, "tracking_number": tracking_number}
        )
        return True
    except:
        return False

async def send_restock_alert_sms(phone: str, product_name: str) -> bool:
    """Send restock notification SMS"""
    try:
        await send_templated_sms(
            phone_number=phone,
            template="restock",
            variables={"product_name": product_name}
        )
        return True
    except:
        return False
