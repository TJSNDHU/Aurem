"""
Milestone Unlock System & Anti-Fraud Suite
Extracted from server.py for modularity.
"""

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)

_db = None

# Configuration
MILESTONE_REFERRAL_THRESHOLD = 10
MILESTONE_DISCOUNT_PERCENT = 30
MILESTONE_EMAIL_TRIGGER = 8

# Anti-fraud configuration
FRAUD_MAX_REFERRALS_PER_IP = 3
FRAUD_MAX_REFERRALS_PER_DEVICE = 3
FRAUD_SUSPICIOUS_TIME_WINDOW = 3600


def set_db(database):
    global _db
    _db = database


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


async def generate_device_fingerprint(
    request: Request, client_fingerprint: str = None
) -> str:
    """Generate a device fingerprint from request headers and client-provided data"""
    components = [
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.headers.get("accept-encoding", ""),
        client_fingerprint or "",
    ]
    fingerprint_str = "|".join(components)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]


async def check_referral_fraud(
    referrer_code: str,
    new_user_email: str,
    ip_address: str,
    device_fingerprint: str,
) -> dict:
    """
    Advanced fraud detection for referral system.
    Returns: {"is_fraud": bool, "reason": str, "risk_score": int}
    """
    db = _get_db()
    risk_score = 0
    reasons = []

    # 1. Check if this IP already referred for this referrer
    ip_referrals = await db.verified_referrals.count_documents(
        {"referrer_code": referrer_code, "ip_address": ip_address}
    )
    if ip_referrals >= FRAUD_MAX_REFERRALS_PER_IP:
        risk_score += 50
        reasons.append(f"IP {ip_address[:8]}*** has {ip_referrals} referrals for this code")

    # 2. Check device fingerprint
    if device_fingerprint:
        device_referrals = await db.verified_referrals.count_documents(
            {"referrer_code": referrer_code, "device_fingerprint": device_fingerprint}
        )
        if device_referrals >= FRAUD_MAX_REFERRALS_PER_DEVICE:
            risk_score += 60
            reasons.append(f"Same device has {device_referrals} referrals")

    # 3. Check email domain patterns (disposable emails)
    email_domain = new_user_email.split("@")[-1].lower()
    disposable_domains = [
        "tempmail", "throwaway", "guerrilla", "mailinator", "10minute",
        "yopmail", "fakeinbox", "trashmail", "getnada", "maildrop",
    ]
    if any(d in email_domain for d in disposable_domains):
        risk_score += 70
        reasons.append("Disposable email domain detected")

    # 4. Check velocity
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_referrals = await db.verified_referrals.count_documents(
        {"referrer_code": referrer_code, "verified_at": {"$gte": one_hour_ago.isoformat()}}
    )
    if recent_referrals >= 3:
        risk_score += 30
        reasons.append(f"{recent_referrals} referrals in last hour (velocity alert)")

    # 5. Check if referred email is similar to referrer email (self-referral)
    referrer = await db.founding_members.find_one(
        {"referral_code": referrer_code}, {"email": 1, "_id": 0}
    )
    if not referrer:
        referrer = await db.waitlist.find_one(
            {"referral_code": referrer_code}, {"email": 1, "_id": 0}
        )

    if referrer:
        referrer_email = referrer.get("email", "").lower()
        if referrer_email and new_user_email:
            referrer_name = referrer_email.split("@")[0]
            new_name = new_user_email.split("@")[0]
            if referrer_name in new_name or new_name in referrer_name:
                if len(referrer_name) > 3 and len(new_name) > 3:
                    risk_score += 40
                    reasons.append("Email similarity detected (possible self-referral)")

    is_fraud = risk_score >= 70
    return {
        "is_fraud": is_fraud,
        "risk_score": risk_score,
        "reasons": reasons,
        "action": "block" if is_fraud else ("review" if risk_score >= 40 else "allow"),
    }


async def get_milestone_progress(referrer_code: str) -> dict:
    """Get the milestone progress for a referrer"""
    db = _get_db()
    count = await db.verified_referrals.count_documents({"referrer_code": referrer_code})

    member = await db.founding_members.find_one(
        {"referral_code": referrer_code},
        {"_id": 0, "milestone_unlocked": 1, "unlock_code": 1, "unlock_date": 1},
    )
    if not member:
        member = await db.waitlist.find_one(
            {"referral_code": referrer_code},
            {"_id": 0, "milestone_unlocked": 1, "unlock_code": 1, "unlock_date": 1},
        )

    unlocked = member.get("milestone_unlocked", False) if member else False
    unlock_code = member.get("unlock_code") if member else None

    return {
        "count": count,
        "threshold": MILESTONE_REFERRAL_THRESHOLD,
        "remaining": max(0, MILESTONE_REFERRAL_THRESHOLD - count),
        "progress_percent": min(100, int((count / MILESTONE_REFERRAL_THRESHOLD) * 100)),
        "unlocked": unlocked,
        "unlock_code": unlock_code if unlocked else None,
        "discount_percent": MILESTONE_DISCOUNT_PERCENT if unlocked else 0,
    }


async def unlock_milestone_discount(referrer_code: str) -> dict:
    """Unlock the 30% discount when milestone is reached"""
    db = _get_db()
    unique_code = f"UNLOCK-{referrer_code[:6]}-{secrets.token_hex(3).upper()}"

    unlock_data = {
        "milestone_unlocked": True,
        "unlock_code": unique_code,
        "unlock_date": datetime.now(timezone.utc).isoformat(),
        "permanent_discount_percent": MILESTONE_DISCOUNT_PERCENT,
    }

    await db.founding_members.update_one(
        {"referral_code": referrer_code}, {"$set": unlock_data}
    )
    await db.waitlist.update_one(
        {"referral_code": referrer_code}, {"$set": unlock_data}
    )

    member = await db.founding_members.find_one(
        {"referral_code": referrer_code},
        {"_id": 0, "email": 1, "name": 1, "phone": 1, "whatsapp": 1},
    )
    if not member:
        member = await db.waitlist.find_one(
            {"referral_code": referrer_code},
            {"_id": 0, "email": 1, "name": 1, "phone": 1, "whatsapp": 1},
        )

    if member:
        if member.get("email"):
            await send_milestone_unlocked_email(
                member["email"], member.get("name", ""), unique_code
            )

        whatsapp_number = member.get("whatsapp") or member.get("phone")
        if whatsapp_number:
            try:
                from services.twilio_service import send_milestone_unlocked_whatsapp
                await send_milestone_unlocked_whatsapp(
                    phone=whatsapp_number,
                    name=member.get("name", ""),
                    unlock_code=unique_code,
                )
                logger.info(f"Sent milestone unlocked WhatsApp to {referrer_code}")
            except Exception:
                pass

        try:
            from services.social_proof import generate_social_proof_post
            social_post = await generate_social_proof_post(
                member.get("name", "A member"), MILESTONE_REFERRAL_THRESHOLD
            )
            await db.marketing_social_posts.insert_one({
                "id": str(uuid.uuid4()),
                "type": "milestone_unlock",
                "content": social_post,
                "referrer_code": referrer_code,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "posted": False,
            })
        except Exception:
            pass

    logger.info(f"Milestone unlocked for {referrer_code}: {unique_code}")
    return {"unlock_code": unique_code, "discount_percent": MILESTONE_DISCOUNT_PERCENT}


async def verify_referral_for_milestone(
    referrer_code: str,
    referred_email: str,
    ip_address: str,
    device_fingerprint: str = None,
) -> dict:
    """
    Verify a referral counts toward the 10-referral milestone.
    """
    db = _get_db()

    existing = await db.verified_referrals.find_one(
        {"referrer_code": referrer_code, "referred_email": referred_email.lower()},
        {"_id": 0},
    )
    if existing:
        return {
            "success": False,
            "reason": "Referral already counted",
            "milestone_progress": await get_milestone_progress(referrer_code),
        }

    fraud_check = await check_referral_fraud(
        referrer_code, referred_email, ip_address, device_fingerprint
    )
    if fraud_check["is_fraud"]:
        logger.warning(
            f"Fraud detected for referral {referrer_code} -> {referred_email}: {fraud_check['reasons']}"
        )
        return {
            "success": False,
            "reason": "Referral flagged for review",
            "fraud_detected": True,
            "milestone_progress": await get_milestone_progress(referrer_code),
        }

    bio_scan = await db.bio_scans.find_one(
        {"email": referred_email.lower()},
        {"_id": 0, "id": 1, "created_at": 1, "whatsapp": 1, "whatsapp_verified": 1, "phone": 1},
    )
    if not bio_scan:
        return {
            "success": False,
            "reason": "Referral must complete Bio-Age Scan to count",
            "pending": True,
            "milestone_progress": await get_milestone_progress(referrer_code),
        }

    # WhatsApp phone verification
    phone_hash = None
    referred_phone = bio_scan.get("whatsapp") or bio_scan.get("phone")
    if referred_phone:
        try:
            from services.twilio_service import verify_referral_phone
            phone_verification = await verify_referral_phone(referred_phone, referrer_code, db)
            if not phone_verification.get("valid"):
                logger.warning(
                    f"WhatsApp fraud check failed for {referrer_code} -> {referred_email}: {phone_verification.get('reason')}"
                )
                return {
                    "success": False,
                    "reason": phone_verification.get("reason", "Phone verification failed"),
                    "fraud_type": phone_verification.get("fraud_type"),
                    "milestone_progress": await get_milestone_progress(referrer_code),
                }
            phone_hash = phone_verification.get("phone_hash")
        except ImportError:
            pass

    verified_referral = {
        "id": str(uuid.uuid4()),
        "referrer_code": referrer_code,
        "referred_email": referred_email.lower(),
        "bio_scan_id": bio_scan.get("id"),
        "ip_address": ip_address,
        "device_fingerprint": device_fingerprint,
        "phone_hash": phone_hash,
        "whatsapp_verified": bio_scan.get("whatsapp_verified", False),
        "fraud_risk_score": fraud_check["risk_score"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.verified_referrals.insert_one(verified_referral)

    await db.founding_members.update_one(
        {"referral_code": referrer_code}, {"$inc": {"verified_referral_count": 1}}
    )
    await db.waitlist.update_one(
        {"referral_code": referrer_code}, {"$inc": {"verified_referral_count": 1}}
    )

    progress = await get_milestone_progress(referrer_code)

    # Send WhatsApp notification
    referrer_member = await db.founding_members.find_one(
        {"referral_code": referrer_code},
        {"_id": 0, "phone": 1, "whatsapp": 1, "name": 1},
    )
    if not referrer_member:
        referrer_member = await db.waitlist.find_one(
            {"referral_code": referrer_code},
            {"_id": 0, "phone": 1, "whatsapp": 1, "name": 1},
        )

    referrer_phone = (
        referrer_member.get("whatsapp") or referrer_member.get("phone")
        if referrer_member else None
    )
    if referrer_phone:
        try:
            from services.twilio_service import send_milestone_new_referral_whatsapp
            await send_milestone_new_referral_whatsapp(
                phone=referrer_phone,
                name=referrer_member.get("name", ""),
                count=progress["count"],
                threshold=progress["threshold"],
                referral_code=referrer_code,
            )
            logger.info(f"Sent new referral WhatsApp to {referrer_code}")
        except Exception:
            pass

    if progress["count"] >= MILESTONE_REFERRAL_THRESHOLD and not progress["unlocked"]:
        await unlock_milestone_discount(referrer_code)
        progress = await get_milestone_progress(referrer_code)
    elif progress["count"] == MILESTONE_EMAIL_TRIGGER:
        await send_milestone_almost_there_email(referrer_code, progress["count"])

    return {"success": True, "milestone_progress": progress}


async def send_milestone_almost_there_email(referrer_code: str, current_count: int):
    """Send the 8/10 'Almost There' notification"""
    db = _get_db()
    member = await db.founding_members.find_one(
        {"referral_code": referrer_code},
        {"_id": 0, "email": 1, "name": 1, "phone": 1, "whatsapp": 1},
    )
    if not member:
        member = await db.waitlist.find_one(
            {"referral_code": referrer_code},
            {"_id": 0, "email": 1, "name": 1, "phone": 1, "whatsapp": 1},
        )

    if not member:
        return

    remaining = MILESTONE_REFERRAL_THRESHOLD - current_count
    name = member.get("name", "").split()[0] if member.get("name") else "there"

    whatsapp_number = member.get("whatsapp") or member.get("phone")
    if whatsapp_number:
        try:
            from services.twilio_service import send_milestone_almost_there_whatsapp
            await send_milestone_almost_there_whatsapp(
                phone=whatsapp_number,
                name=member.get("name", ""),
                count=current_count,
                threshold=MILESTONE_REFERRAL_THRESHOLD,
                referral_code=referrer_code,
            )
            logger.info(f"Sent milestone 'almost there' WhatsApp to {referrer_code}")
        except Exception:
            pass

    try:
        from services.email_engine import resend  # iter 326x defensive
        RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
        if not RESEND_API_KEY or not member.get("email"):
            return

        FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
        resend.emails.send({
            "from": "AUREM <noreply@aurem.live>",
            "to": member["email"],
            "subject": f"You're SO Close! Just {remaining} Referrals Away from 30% OFF Forever",
            "html": f"""
            <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #ffffff; border-radius: 12px; overflow: hidden;">
                <div style="padding: 40px 30px; text-align: center;">
                    <h1 style="font-size: 28px; margin: 0 0 10px; color: #D4AF37;">You're Almost There, {name}!</h1>
                    <p style="font-size: 16px; color: #cccccc; margin: 0;">Your 30% Lifetime Discount is within reach.</p>
                </div>
                <div style="background: rgba(212, 175, 55, 0.1); padding: 30px; text-align: center;">
                    <div style="font-size: 48px; font-weight: bold; color: #D4AF37;">{current_count} / {MILESTONE_REFERRAL_THRESHOLD}</div>
                    <p style="font-size: 18px; color: #ffffff; margin: 0;">
                        <strong style="color: #D4AF37;">Only {remaining} more referral{'s' if remaining > 1 else ''}</strong> to unlock your permanent 30% discount!
                    </p>
                </div>
                <div style="padding: 30px; text-align: center;">
                    <a href="{FRONTEND_URL}/Bio-Age-Repair-Scan?ref={referrer_code}" style="display: inline-block; background: linear-gradient(135deg, #D4AF37, #B8860B); color: #000; padding: 15px 40px; border-radius: 30px; text-decoration: none; font-weight: bold; font-size: 16px;">
                        Get Your Shareable Link
                    </a>
                </div>
            </div>
            """,
        })
        logger.info(f"Sent milestone 'almost there' email to {member['email']}")
    except Exception as e:
        logger.error(f"Failed to send milestone email: {e}")


async def send_milestone_unlocked_email(email: str, name: str, unlock_code: str):
    """Send the 'Congratulations - You Unlocked 30%' email"""
    try:
        from services.email_engine import resend  # iter 326x defensive
        RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
        if not RESEND_API_KEY:
            return

        first_name = name.split()[0] if name else "Champion"
        FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
        resend.emails.send({
            "from": "AUREM <noreply@aurem.live>",
            "to": email,
            "subject": "UNLOCKED! Your 30% Lifetime Discount is Live",
            "html": f"""
            <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #ffffff; border-radius: 12px; overflow: hidden;">
                <div style="padding: 40px 30px; text-align: center; background: linear-gradient(135deg, rgba(212, 175, 55, 0.3), rgba(184, 134, 11, 0.1));">
                    <h1 style="font-size: 32px; margin: 0 0 10px; color: #D4AF37;">Congratulations, {first_name}!</h1>
                    <p style="font-size: 18px; color: #ffffff; margin: 0;">You've unlocked your <strong>30% Lifetime Discount</strong>!</p>
                </div>
                <div style="padding: 30px; text-align: center;">
                    <div style="background: rgba(212, 175, 55, 0.15); border: 2px solid #D4AF37; border-radius: 12px; padding: 25px; margin-bottom: 25px;">
                        <p style="margin: 0 0 5px; color: #888; font-size: 12px; text-transform: uppercase;">Your Exclusive Code</p>
                        <p style="margin: 0; font-size: 32px; font-weight: bold; color: #D4AF37; letter-spacing: 2px;">{unlock_code}</p>
                    </div>
                    <a href="{FRONTEND_URL}/shop" style="display: inline-block; background: linear-gradient(135deg, #D4AF37, #B8860B); color: #000; padding: 15px 40px; border-radius: 30px; text-decoration: none; font-weight: bold; font-size: 16px;">
                        Shop Now with 30% OFF
                    </a>
                </div>
            </div>
            """,
        })
        logger.info(f"Sent milestone unlocked email to {email}")
    except Exception as e:
        logger.error(f"Failed to send unlock email: {e}")
