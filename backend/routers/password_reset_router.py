"""
Email Verification Router
=========================
Email verification flow for AUREM users.
Email sending is MOCKED (logs to console) — plug in Resend later.
"""

import os
import secrets
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth - Email Verification"])

_db = None


def set_db(database):
    global _db
    _db = database


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


async def send_email_mock(to: str, subject: str, body: str):
    """Mock email sender - logs to console. Replace with Resend API later."""
    logger.info(f"[EMAIL MOCK] To: {to} | Subject: {subject} | Body: {body}")


@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequest):
    """Verify email address using token."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    token_doc = await _db.email_verification_tokens.find_one(
        {"token": body.token}, {"_id": 0}
    )

    if not token_doc:
        raise HTTPException(400, "Invalid verification token")

    if token_doc.get("verified"):
        return {"message": "Email already verified"}

    expires_at = token_doc.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(400, "Verification link has expired. Please request a new one.")

    await _db.users.update_one(
        {"email": token_doc["email"]},
        {"$set": {"email_verified": True, "verified_at": datetime.now(timezone.utc).isoformat()}}
    )

    await _db.email_verification_tokens.update_one(
        {"token": body.token},
        {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc)}}
    )

    logger.info(f"[AUTH] Email verified for {token_doc['email']}")
    return {"message": "Email verified successfully!"}


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest):
    """Resend email verification link."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    email = body.email.lower().strip()
    user = await _db.users.find_one({"email": email}, {"_id": 0})

    if not user:
        return {"message": "If an account exists, a verification email has been sent."}

    if user.get("email_verified"):
        return {"message": "Email is already verified."}

    token = secrets.token_urlsafe(32)
    await _db.email_verification_tokens.insert_one({
        "token": token,
        "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        "verified": False,
        "created_at": datetime.now(timezone.utc),
    })

    verify_link = f"/verify-email?token={token}"

    await send_email_mock(
        to=email,
        subject="AUREM - Verify Your Email",
        body=f"Click this link to verify your email: {verify_link}",
    )

    logger.info(f"[AUTH] Verification token sent to {email}: {verify_link}")
    return {"message": "If an account exists, a verification email has been sent."}
