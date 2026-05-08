"""
Multi-Tenant Provisioning Service — Per-Client Integration Profiles
====================================================================
Each client gets their own integration profile with:
- SMTP email config (host, port, user, pass) with test connection
- WhatsApp session (QR-based via Evolution API / local bridge)
- Unique activation tokens for self-onboarding
- Scoped sending: never uses process.env, always client config

Zero cost: clients use their own SMTP/WhatsApp credentials.
"""

import os
import uuid
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


async def provision_client(tenant_id: str, email: str, company_name: str = "") -> Dict:
    """
    Create a new integration profile for a client.
    Called when a client selects a plan or is manually onboarded.
    """
    if _db is None:
        return {"error": "Database not connected"}

    existing = await _db.user_integrations.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if existing:
        return {"status": "exists", "profile": existing}

    instance_id = f"sov-{uuid.uuid4().hex[:12]}"
    activation_token = _generate_activation_token(tenant_id)

    profile = {
        "tenant_id": tenant_id,
        "instance_id": instance_id,
        "email": email,
        "company_name": company_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_activation",

        # Email Integration
        "email_config": {
            "smtp_host": "",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_pass": "",
            "smtp_secure": True,
            "from_name": company_name or "ORA AI",
            "from_email": "",
            "verified": False,
            "last_test": None,
        },

        # WhatsApp Integration
        "whatsapp_config": {
            "session_id": "",
            "phone_number": "",
            "connected": False,
            "qr_generated_at": None,
            "last_active": None,
            "provider": "evolution_api",
        },

        # Activation
        "activation_token": activation_token,
        "activation_expires": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "activated_at": None,

        # Usage tracking
        "emails_sent": 0,
        "whatsapp_sent": 0,
        "last_email_at": None,
        "last_whatsapp_at": None,
    }

    await _db.user_integrations.insert_one(profile)
    logger.info(f"[Provisioning] Client provisioned: {tenant_id} → {instance_id}")

    # iter 282aj — fire-and-forget LinkedIn case_study post on every onboard.
    try:
        import asyncio as _aio
        from services.linkedin_publisher import publish_linkedin_post
        _aio.create_task(publish_linkedin_post(_db, "case_study", {
            "business_name": company_name or email.split("@")[0],
            "category":      "general",
            "city":          "",
            "result":        "just launched on AUREM",
            "lead_id":       tenant_id,
        }))
    except Exception as e:
        logger.debug(f"[Provisioning] LinkedIn case_study dispatch skipped: {e}")

    return {"status": "provisioned", "instance_id": instance_id, "activation_token": activation_token}


def _generate_activation_token(tenant_id: str) -> str:
    """Generate a secure, unique activation token."""
    secret = os.getenv("JWT_SECRET", "aurem-default-secret")
    payload = f"{tenant_id}:{uuid.uuid4().hex}:{datetime.now(timezone.utc).isoformat()}"
    token = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"act_{token}"


async def get_client_integrations(tenant_id: str) -> Optional[Dict]:
    """Get a client's integration profile."""
    if _db is None:
        return None
    return await _db.user_integrations.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )


async def get_by_activation_token(token: str) -> Optional[Dict]:
    """Look up a client profile by activation token."""
    if _db is None:
        return None
    return await _db.user_integrations.find_one(
        {"activation_token": token}, {"_id": 0}
    )


async def update_email_config(tenant_id: str, config: Dict) -> Dict:
    """Update a client's SMTP email configuration."""
    if _db is None:
        return {"error": "Database not connected"}

    update = {
        "email_config.smtp_host": config.get("smtp_host", ""),
        "email_config.smtp_port": config.get("smtp_port", 587),
        "email_config.smtp_user": config.get("smtp_user", ""),
        "email_config.smtp_pass": config.get("smtp_pass", ""),
        "email_config.smtp_secure": config.get("smtp_secure", True),
        "email_config.from_name": config.get("from_name", ""),
        "email_config.from_email": config.get("from_email", ""),
    }

    await _db.user_integrations.update_one(
        {"tenant_id": tenant_id},
        {"$set": update}
    )
    return {"status": "updated"}


async def test_email_connection(tenant_id: str) -> Dict:
    """Test the client's SMTP connection."""
    profile = await get_client_integrations(tenant_id)
    if not profile:
        return {"success": False, "error": "Profile not found"}

    ec = profile.get("email_config", {})
    if not ec.get("smtp_host") or not ec.get("smtp_user"):
        return {"success": False, "error": "SMTP not configured — add your email server details first"}

    try:
        import aiosmtplib
        smtp = aiosmtplib.SMTP(
            hostname=ec["smtp_host"],
            port=ec["smtp_port"],
            use_tls=ec.get("smtp_secure", True),
        )
        await smtp.connect()
        await smtp.login(ec["smtp_user"], ec["smtp_pass"])
        await smtp.quit()

        # Mark as verified
        await _db.user_integrations.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "email_config.verified": True,
                "email_config.last_test": datetime.now(timezone.utc).isoformat(),
                "status": "active" if profile.get("whatsapp_config", {}).get("connected") else "email_active",
            }}
        )
        return {"success": True, "message": "SMTP connection verified"}
    except ImportError:
        # aiosmtplib not installed — do basic socket check
        import socket
        try:
            sock = socket.create_connection((ec["smtp_host"], ec["smtp_port"]), timeout=5)
            sock.close()
            await _db.user_integrations.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "email_config.verified": True,
                    "email_config.last_test": datetime.now(timezone.utc).isoformat(),
                }}
            )
            return {"success": True, "message": "SMTP port reachable (full auth test requires aiosmtplib)"}
        except Exception as e:
            return {"success": False, "error": f"Cannot reach {ec['smtp_host']}:{ec['smtp_port']}: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def init_whatsapp_session(tenant_id: str) -> Dict:
    """Initialize a WhatsApp session for the client (QR code generation)."""
    profile = await get_client_integrations(tenant_id)
    if not profile:
        return {"error": "Profile not found"}

    session_id = f"wa-{tenant_id}-{uuid.uuid4().hex[:8]}"

    await _db.user_integrations.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "whatsapp_config.session_id": session_id,
            "whatsapp_config.qr_generated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    return {
        "session_id": session_id,
        "status": "qr_pending",
        "instructions": "Scan the QR code with your WhatsApp mobile app to connect this session.",
        "note": "WhatsApp Web multi-device bridge will be activated when Legion comes online.",
    }


async def send_scoped_email(tenant_id: str, to_email: str, subject: str, body: str) -> Dict:
    """
    Send an email using the CLIENT'S own SMTP config.
    Never uses process.env — always scoped to the tenant.
    """
    profile = await get_client_integrations(tenant_id)
    if not profile:
        return {"success": False, "error": "Client profile not found"}

    ec = profile.get("email_config", {})
    if not ec.get("verified"):
        return {"success": False, "error": "Email not verified. Complete the Connection Wizard first."}

    try:
        import aiosmtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{ec.get('from_name', 'ORA AI')} <{ec.get('from_email', ec['smtp_user'])}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        await aiosmtplib.send(
            msg,
            hostname=ec["smtp_host"],
            port=ec["smtp_port"],
            username=ec["smtp_user"],
            password=ec["smtp_pass"],
            use_tls=ec.get("smtp_secure", True),
        )

        # Track usage
        await _db.user_integrations.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"emails_sent": 1}, "$set": {"last_email_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"success": True, "message": f"Email sent to {to_email} via {ec['smtp_host']}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def seed_existing_tenants():
    """Create integration profiles for existing tenant_customers who don't have one yet."""
    if _db is None:
        return 0

    tenants = await _db.tenant_customers.find({}, {"_id": 0, "tenant_id": 1, "email": 1, "company_name": 1}).to_list(length=100)
    seeded = 0
    for t in tenants:
        tid = t.get("tenant_id")
        if not tid:
            continue
        existing = await _db.user_integrations.find_one({"tenant_id": tid})
        if not existing:
            await provision_client(tid, t.get("email", ""), t.get("company_name", ""))
            seeded += 1

    if seeded > 0:
        logger.info(f"[Provisioning] Seeded {seeded} existing tenants with integration profiles")
    return seeded
