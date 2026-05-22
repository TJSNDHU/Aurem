"""
AUREM Welcome Package Service
Auto-triggered on signup. Sends welcome email (mocked until SendGrid),
creates in-app notification, sets welcome card flag.
"""
import os
import io
import base64
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db


def _generate_qr_base64(business_id: str) -> str:
    """Generate QR code as base64 string."""
    try:
        import qrcode
        base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
        url = f"{base_url}/ora?id={business_id}"
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#C9A84C", back_color="#050507")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.warning(f"[WELCOME] QR generation failed: {e}")
        return ""


def _render_email_template(data: dict) -> str:
    """Render welcome email HTML template."""
    try:
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "welcome_email.html")
        with open(template_path, "r") as f:
            html = f.read()
        for key, val in data.items():
            html = html.replace("{{" + key + "}}", str(val))
        return html
    except Exception as e:
        logger.warning(f"[WELCOME] Template render failed: {e}")
        return ""


# iter 322ab — reusable Resend sender so other handlers (e.g. the
# homepage instant-trial flow) can fire the same welcome email without
# duplicating the integration code.
async def _send_via_resend(to: str, subject: str, html_body: str,
                            email_data: dict | None = None) -> dict:
    """Send an HTML email via Resend. Logs to db.sent_emails. Best-effort —
    never raises. Returns {ok, status, resend_id, error}."""
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_addr = os.environ.get("RESEND_FROM", "AUREM <welcome@aurem.live>")
    send_status = "skipped_no_key"
    resend_id = None
    send_error = None
    try:
        if resend_key:
            from services.email_engine import resend as _resend  # iter 326x defensive
            _resend.api_key = resend_key

            def _do_send():
                return _resend.Emails.send({
                    "from": from_addr,
                    "to": [to],
                    "subject": subject,
                    "html": html_body or f"<p>{subject}</p>",
                })

            import asyncio as _asyncio
            result = await _asyncio.to_thread(_do_send)
            resend_id = (result or {}).get("id")
            send_status = "sent" if resend_id else "accepted_no_id"
        else:
            logger.warning("[email] RESEND_API_KEY missing — email not delivered")
    except Exception as _e:
        send_error = str(_e)[:200]
        send_status = "send_error"
        logger.warning(f"[email] Resend send failed: {_e}")

    if _db is not None:
        try:
            await _db.sent_emails.insert_one({
                "to": to,
                "subject": subject,
                "template": "welcome_email",
                "data": email_data or {},
                "html_preview": (html_body or "")[:500],
                "status": send_status,
                "resend_id": resend_id,
                "error": send_error,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            logger.debug(f"[email] sent_emails insert skipped: {e}")
    return {"ok": send_status == "sent", "status": send_status,
            "resend_id": resend_id, "error": send_error}


async def send_welcome_package(tenant_id: str, user_doc: dict = None):
    """Send complete welcome package: email + notification + welcome card flag."""
    if _db is None:
        logger.warning("[WELCOME] No DB available")
        return

    if not user_doc:
        user_doc = await _db.users.find_one(
            {"$or": [{"id": tenant_id}, {"tenant_id": tenant_id}, {"email": tenant_id}]},
            {"_id": 0}
        )
        if not user_doc:
            user_doc = await _db.platform_users.find_one(
                {"$or": [{"id": tenant_id}, {"tenant_id": tenant_id}, {"email": tenant_id}]},
                {"_id": 0}
            )
    if not user_doc:
        logger.warning(f"[WELCOME] User not found for {tenant_id}")
        return

    bid = user_doc.get("business_id", "")
    if not bid:
        logger.warning(f"[WELCOME] No business_id for {tenant_id}")
        return

    email = user_doc.get("email", "")
    first_name = user_doc.get("first_name") or user_doc.get("full_name", "").split(" ")[0] or "there"
    business_name = user_doc.get("company") or user_doc.get("company_name") or user_doc.get("business_name") or first_name
    now = datetime.now(timezone.utc)

    qr_b64 = _generate_qr_base64(bid)

    # ═══════════════════════════════════════════════════════════
    # API Key — generate per-customer pixel key (Feb 2026)
    # ═══════════════════════════════════════════════════════════
    api_key_display = ""
    try:
        existing = await _db.api_keys.find_one({"email": email, "active": True}, {"_id": 0, "key_preview": 1})
        if not existing:
            import secrets as _secrets, hashlib as _hashlib
            api_key_display = f"rr_live_{_secrets.token_hex(20)}"
            key_hash = _hashlib.sha256(api_key_display.encode()).hexdigest()
            await _db.api_keys.insert_one({
                "key_hash": key_hash,
                "key_preview": api_key_display[:12] + "..." + api_key_display[-4:],
                "client_name": business_name,
                "tenant_id": tenant_id,
                "email": email,
                "brand": "aurem",
                "tier": "starter",
                "monthly_limit": 500,
                "used_this_month": 0,
                "total_used": 0,
                "active": True,
                "created_at": now.isoformat(),
            })
            logger.info(f"[WELCOME] Generated API key for {email}")
    except Exception as e:
        logger.warning(f"[WELCOME] API key generation failed: {e}")

    base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
    # Pixel install snippet (shown only when a new key was generated)
    pixel_snippet = ""
    if api_key_display:
        pixel_snippet = (
            f'<script src="{base_url}/api/pixel/aurem-pixel.js" '
            f'data-aurem-key="{api_key_display}"></script>'
        )

    # iter 322z — pull trial_ends_at from billing for the welcome template.
    # This is what the user opens the email to see ("how long do I have?").
    trial_ends_iso = ""
    trial_ends_human = ""
    try:
        from datetime import timedelta as _td
        billing = await _db.aurem_billing.find_one(
            {"$or": [{"business_id": bid}, {"email": email}]},
            {"_id": 0, "trial_ends_at": 1},
        )
        ttl = (billing or {}).get("trial_ends_at")
        if isinstance(ttl, str):
            try:
                ttl = datetime.fromisoformat(ttl.replace("Z", "+00:00"))
            except Exception:
                ttl = None
        if not isinstance(ttl, datetime):
            ttl = now + _td(days=7)  # fallback to today + 7d per spec
        trial_ends_iso = ttl.isoformat()
        trial_ends_human = ttl.strftime("%B %d, %Y")
    except Exception:
        from datetime import timedelta as _td
        ttl = now + _td(days=7)
        trial_ends_iso = ttl.isoformat()
        trial_ends_human = ttl.strftime("%B %d, %Y")

    email_data = {
        "first_name": first_name,
        "business_name": business_name,
        "business_id": bid,
        # iter 322z — link directly to /dashboard so a freshly-signed-up
        # customer doesn't bounce through /login (we already auto-issued
        # the JWT in the register response and the SPA picks it up from
        # localStorage).
        "dashboard_url": f"{base_url}/dashboard",
        "ora_url": f"{base_url}/ora?id={bid}",
        "api_key": api_key_display or "(already issued — check dashboard)",
        "pixel_snippet": pixel_snippet or "(already issued — retrieve from your dashboard → Settings → API Keys)",
        "trial_ends_at": trial_ends_iso,
        "trial_ends_human": trial_ends_human,
        "support_email": "ora@aurem.live",
    }
    html_body = _render_email_template(email_data)

    # ═══════════════════════════════════════════════════════════
    # Actual Resend delivery (Iter 320.1 — removed "mocked" status).
    # The SDK is sync; run in a thread so we don't block the loop.
    # ═══════════════════════════════════════════════════════════
    send_status = "mocked"
    resend_id = None
    send_error = None
    try:
        from services.email_engine import resend as _resend  # iter 326x defensive
        resend_key = os.environ.get("RESEND_API_KEY", "").strip()
        if resend_key and email:
            _resend.api_key = resend_key
            from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <hello@aurem.live>")
            subject_line = f"Welcome to AUREM — Your Business ID: {bid}"

            def _do_send():
                return _resend.Emails.send({
                    "from": from_addr,
                    "to": [email],
                    "subject": subject_line,
                    "html": html_body or f"<p>Welcome — your Business ID is {bid}.</p>",
                })

            import asyncio as _asyncio
            result = await _asyncio.to_thread(_do_send)
            resend_id = (result or {}).get("id")
            send_status = "sent" if resend_id else "accepted_no_id"
            logger.info(f"[WELCOME] Resend delivered to {email[:5]}*** msg_id={resend_id}")
        elif not resend_key:
            send_status = "skipped_no_key"
            logger.warning("[WELCOME] RESEND_API_KEY missing — email not delivered")
    except Exception as _e:
        send_error = str(_e)[:200]
        send_status = "send_error"
        logger.warning(f"[WELCOME] Resend send failed: {_e}")

    await _db.sent_emails.insert_one({
        "tenant_id": tenant_id,
        "to": email,
        "subject": f"Welcome to AUREM — Your Business ID: {bid}",
        "template": "welcome_email",
        "data": email_data,
        "html_preview": html_body[:500] if html_body else "",
        "qr_base64_len": len(qr_b64),
        "status": send_status,
        "resend_id": resend_id,
        "error": send_error,
        "sent_at": now.isoformat(),
    })
    logger.info(f"[WELCOME] Email logged (status={send_status}) for {email} with BID {bid}")

    # In-app notification
    await _db.notifications.insert_one({
        "tenant_id": tenant_id,
        "type": "welcome",
        "title": "Welcome to AUREM",
        "body": f"Your Business ID: {bid}. Check your email for QR code and setup instructions.",
        "action_url": "/ora",
        "read": False,
        "sent_at": now.isoformat(),
    })

    # Set welcome card flag
    update = {"$set": {
        "show_welcome_card": True,
        "welcome_sent_at": now.isoformat(),
    }}
    await _db.users.update_one({"email": email}, update)
    await _db.platform_users.update_one({"email": email}, update)

    # ═══════════════════════════════════════════════════════════
    # Welcome SMS (A2P 10DLC live as of 2026-04-30) — best-effort.
    # Skips silently if user has no phone or SMS_DISABLED=true.
    # ═══════════════════════════════════════════════════════════
    sms_status = "skipped_no_phone"
    sms_sid = None
    phone = (
        user_doc.get("phone")
        or user_doc.get("mobile")
        or user_doc.get("whatsapp")
        or ""
    ).strip()
    if phone:
        try:
            from shared.providers.twilio import send_sms
            sms_body = (
                f"AUREM: Welcome {first_name}. "
                f"Your Business ID is {bid}. "
                f"Sign in at {base_url}/login. "
                f"Reply STOP to opt out."
            )
            sms_res = await send_sms(phone, sms_body)
            sms_status = "sent" if sms_res.get("success") else "failed"
            sms_sid = sms_res.get("message_sid")
            logger.info(
                f"[WELCOME] SMS to {phone[:5]}*** status={sms_status} "
                f"sid={sms_sid} channel={sms_res.get('channel', 'sms')}"
            )
        except Exception as _e:
            sms_status = "exception"
            logger.warning(f"[WELCOME] SMS failed: {_e}")

    await _db.sms_logs.insert_one({
        "tenant_id": tenant_id,
        "to": phone,
        "template": "welcome_sms",
        "status": sms_status,
        "message_sid": sms_sid,
        "sent_at": now.isoformat(),
    })

    logger.info(f"[WELCOME] Package sent for {email}: BID={bid}")
    return True
