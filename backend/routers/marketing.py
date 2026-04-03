"""
router: marketing.py
Mount at: /api/marketing
Handles email offer campaigns via Resend.

Add to server.py:
    from routers.marketing import router as marketing_router
    app.include_router(marketing_router, prefix="/api")

Required env vars:
    RESEND_API_KEY
"""

import os
import re
import logging
from typing import Literal, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import jwt
import resend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/marketing", tags=["marketing"])

# Initialize Resend
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

FROM_EMAIL = "ReRoots <hello@reroots.ca>"


# ── REQUEST SCHEMA ────────────────────────────────────────────────────────────

class SendOfferRequest(BaseModel):
    subject: str
    body: str                                     # plain text or HTML
    discount_code: Optional[str] = None
    recipient_filter: Literal["active", "all", "gold_plus"] = "active"
    # Tokens supported in subject/body: {{name}}, {{tier}}, {{points}}
    template_tokens: list = []


class SubscriberUpdateRequest(BaseModel):
    offers_opt_in: Optional[bool] = None
    status: Optional[str] = None


# ── AUTH HELPER ───────────────────────────────────────────────────────────────

async def get_current_user_from_request(request: Request):
    """Get current user from request - compatible with server.py auth system"""
    JWT_SECRET = os.environ.get("JWT_SECRET") or "dev-secret-key-change-in-production"
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        
        # Get user from database
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            # Try ObjectId
            try:
                user = await db.users.find_one({"_id": ObjectId(user_id)})
            except:
                pass
        
        return user
    except Exception as e:
        return None


def get_db():
    """Get database connection"""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "reroots")
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, html_content: str, name: str = None):
    """Send email via Resend - can be imported and used elsewhere"""
    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured - email not sent")
        return False
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to_email,
            "subject": subject,
            "html": html_content
        })
        logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def personalize(text: str, user: dict, discount_code: str = "") -> str:
    """Replace {{token}} placeholders with real user values."""
    name = user.get("name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
    replacements = {
        "{{name}}": name or "Valued Member",
        "{{first_name}}": user.get("first_name", name.split()[0] if name else ""),
        "{{tier}}": user.get("tier", "Silver"),
        "{{points}}": str(user.get("loyalty_points", 0)),
        "{{discount_code}}": discount_code or "",
        "{{email}}": user.get("email", ""),
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def build_html(body_text: str, subject: str, discount_code: str = "") -> str:
    """
    Wrap plain text body in a minimal branded HTML email.
    If body already contains HTML tags, use it as-is.
    """
    is_html = bool(re.search(r"<[a-z][\s\S]*>", body_text, re.IGNORECASE))
    if is_html:
        content = body_text
    else:
        # Convert newlines to <br> for plain text bodies
        content = "<br>".join(body_text.splitlines())

    discount_block = ""
    if discount_code:
        discount_block = f"""
        <div style="margin:28px 0;text-align:center;">
            <div style="display:inline-block;background:#1a1408;border:1px solid #C9A86E;
                border-radius:6px;padding:14px 32px;">
                <p style="font-family:'Gill Sans',sans-serif;font-size:11px;
                    letter-spacing:0.2em;color:#8A6B38;text-transform:uppercase;margin:0 0 6px;">
                    Exclusive Offer Code
                </p>
                <p style="font-family:Georgia,serif;font-size:22px;color:#E2C98A;
                    letter-spacing:0.12em;margin:0;">
                    {discount_code}
                </p>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#060608;margin:0;padding:0;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px;">
      <table width="560" cellpadding="0" cellspacing="0"
        style="background:#0d0d10;border:0.5px solid rgba(201,168,110,0.18);border-radius:16px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#0a0807,#1a1408);
            padding:32px 40px;border-bottom:0.5px solid rgba(201,168,110,0.12);text-align:center;">
          <p style="font-family:'Gill Sans',sans-serif;font-size:10px;letter-spacing:0.35em;
              text-transform:uppercase;color:#8A6B38;margin:0 0 8px;">Biotech Skincare Canada</p>
          <h1 style="font-family:Georgia,serif;font-size:34px;font-weight:300;
              color:#E2C98A;margin:0;letter-spacing:0.04em;">ReRoots</h1>
        </td></tr>

        <!-- Subject -->
        <tr><td style="padding:32px 40px 0;">
          <h2 style="font-family:Georgia,serif;font-size:22px;font-weight:300;
              color:#F0EBE0;margin:0 0 20px;line-height:1.3;">{subject}</h2>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:0 40px 8px;">
          <p style="font-family:Georgia,serif;font-size:15px;color:#A89880;
              line-height:1.8;margin:0;">{content}</p>
        </td></tr>

        <!-- Discount code block -->
        <tr><td style="padding:0 40px;">{discount_block}</td></tr>

        <!-- CTA -->
        <tr><td style="padding:24px 40px 32px;text-align:center;">
          <a href="https://reroots.ca/shop"
            style="display:inline-block;background:linear-gradient(135deg,#8A6B38,#C9A86E);
            color:#060608;text-decoration:none;font-family:'Gill Sans',sans-serif;
            font-size:11px;letter-spacing:0.22em;text-transform:uppercase;
            padding:16px 36px;border-radius:4px;">
            Shop the Collection
          </a>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:20px 40px 28px;border-top:0.5px solid rgba(255,255,255,0.05);
            text-align:center;">
          <p style="font-family:'Gill Sans',sans-serif;font-size:10px;color:#524D45;
              letter-spacing:0.08em;margin:0 0 6px;">reroots.ca · Canadian Biotech Skincare</p>
          <p style="font-family:'Gill Sans',sans-serif;font-size:9px;color:#3a3530;margin:0;">
            You received this because you opted in to ReRoots member offers.
            <a href="https://reroots.ca/unsubscribe"
              style="color:#5C5548;text-decoration:underline;">Unsubscribe</a>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── ENDPOINT ──────────────────────────────────────────────────────────────────

@router.post("/send-offer")
async def send_offer(payload: SendOfferRequest, request: Request):
    """
    Send a marketing offer email to subscribers via Resend.
    Admin/founder only. Personalizes subject + body per recipient.

    Returns:
        { sent_count: int, skipped_count: int, message: str }
    """
    # Check auth
    current_user = await get_current_user_from_request(request)
    if not current_user or current_user.get("role", "customer") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin access required")

    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Resend API key not configured. Set RESEND_API_KEY in environment.",
        )

    db = get_db()

    # ── Build recipient query ─────────────────────────────────────────────────
    query = {"offers_opt_in": {"$ne": False}}

    if payload.recipient_filter == "gold_plus":
        query["tier"] = {"$in": ["Gold", "Diamond", "Elite"]}
    # "all" = no additional filter, "active" = already filtered by offers_opt_in

    recipients = await db.users.find(query).to_list(1000)

    if not recipients:
        return JSONResponse({"sent_count": 0, "skipped_count": 0, "message": "No eligible recipients"})

    # ── Send individually so personalization works ────────────────────────────
    sent_count = 0
    skipped_count = 0
    errors = []

    for user in recipients:
        try:
            user_dict = {
                "name": user.get("name") or f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
                "first_name": user.get("first_name", ""),
                "tier": user.get("tier", "Silver"),
                "loyalty_points": user.get("loyalty_points", 0),
                "email": user.get("email", ""),
            }
            
            personalized_subject = personalize(payload.subject, user_dict, payload.discount_code or "")
            personalized_body = personalize(payload.body, user_dict, payload.discount_code or "")
            html_content = build_html(personalized_body, personalized_subject, payload.discount_code or "")

            # Send via Resend
            resend.Emails.send({
                "from": FROM_EMAIL,
                "to": user.get("email"),
                "subject": personalized_subject,
                "html": html_content
            })
            
            sent_count += 1
            logger.info(f"Offer sent to {user.get('email')}")

        except Exception as e:
            skipped_count += 1
            errors.append({"email": user.get("email"), "error": str(e)})
            logger.error(f"Failed to send offer to {user.get('email')}: {e}")

    if errors:
        logger.warning(f"Send-offer completed with {len(errors)} failures: {errors}")

    return JSONResponse({
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "message": f"Offer sent to {sent_count} subscribers via Resend",
        "errors": errors if errors else [],
    })


# ── SUBSCRIBER TOGGLE ─────────────────────────────────────────────────────────

@router.patch("/subscribers/{user_id}")
async def update_subscriber(user_id: str, payload: SubscriberUpdateRequest, request: Request):
    """
    Toggle a subscriber's offer opt-in status.
    Admin/founder only.

    Returns updated subscriber record.
    """
    current_user = await get_current_user_from_request(request)
    if not current_user or current_user.get("role", "customer") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()

    update_data = {"updated_at": datetime.now(timezone.utc)}
    if payload.offers_opt_in is not None:
        update_data["offers_opt_in"] = payload.offers_opt_in

    try:
        result = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )
    except:
        # Try with string id
        result = await db.users.find_one_and_update(
            {"id": user_id},
            {"$set": update_data},
            return_document=True
        )

    if not result:
        raise HTTPException(status_code=404, detail="Subscriber not found")

    name = result.get("name") or f"{result.get('first_name', '')} {result.get('last_name', '')}".strip()

    return {
        "id": str(result.get("_id", result.get("id", ""))),
        "name": name,
        "email": result.get("email", ""),
        "skin_type": result.get("skin_type", ""),
        "birthday": str(result.get("birthday", "")) if result.get("birthday") else "",
        "tier": result.get("tier", "Silver"),
        "offers_opt_in": result.get("offers_opt_in", True),
        "created_at": str(result.get("created_at", "")) if result.get("created_at") else "",
    }


# ── SUBSCRIBER LIST ───────────────────────────────────────────────────────────

@router.get("/subscribers")
async def get_subscribers(request: Request):
    """
    Return all subscribers (admin only).
    Also accessible at GET /api/crm/subscribers — mount this router at both prefixes
    or add an alias in your CRM router.
    """
    current_user = await get_current_user_from_request(request)
    if not current_user or current_user.get("role", "customer") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    users = await db.users.find().sort("created_at", -1).to_list(1000)
    result = []
    
    for u in users:
        name = u.get("name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        result.append({
            "id": str(u.get("_id", u.get("id", ""))),
            "name": name,
            "email": u.get("email", ""),
            "skin_type": u.get("skin_type", ""),
            "birthday": str(u.get("birthday", "")) if u.get("birthday") else "",
            "tier": u.get("tier", "Silver"),
            "loyalty_points": u.get("loyalty_points", 0),
            "offers_opt_in": u.get("offers_opt_in", True),
            "created_at": str(u.get("created_at", "")) if u.get("created_at") else "",
        })
    
    return result
