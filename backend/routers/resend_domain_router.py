"""
Resend Domain Verification Router
==================================
Manages email domain verification for aurem.live via Resend API.
Provides DNS records for GoDaddy setup and verification status checks.
"""
import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/resend", tags=["Resend Email"])
logger = logging.getLogger(__name__)


def _get_resend_key():
    return os.environ.get("RESEND_API_KEY", "")


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        import jwt
        payload = jwt.decode(
            authorization.replace("Bearer ", ""),
            os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class AddDomainRequest(BaseModel):
    domain: str = "aurem.live"


@router.get("/domains")
async def list_domains(authorization: str = Header(None)):
    """List all domains registered in Resend account."""
    await _auth(authorization)
    key = _get_resend_key()
    if not key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {key}"}
        )
        if resp.status_code == 401:
            return {
                "error": "restricted_key",
                "message": "Current Resend API key is send-only. You need a full-access key to manage domains.",
                "action": "Go to https://resend.com/api-keys and create a new key with 'Full Access' permissions, then inject it via Empire HUD.",
                "manual_dns_records": _get_manual_dns_records("aurem.live"),
            }
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@router.post("/domains")
async def add_domain(req: AddDomainRequest, authorization: str = Header(None)):
    """Register a new domain with Resend for email sending."""
    await _auth(authorization)
    key = _get_resend_key()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"name": req.domain}
        )
        if resp.status_code == 401:
            return {
                "error": "restricted_key",
                "message": "Need full-access Resend API key to add domains.",
                "manual_dns_records": _get_manual_dns_records(req.domain),
            }
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        data = resp.json()
        return {
            "domain_id": data.get("id"),
            "domain": data.get("name"),
            "status": data.get("status"),
            "dns_records": data.get("records", []),
            "godaddy_instructions": _format_godaddy_instructions(data.get("records", []), req.domain),
        }


@router.get("/domains/{domain_id}/verify")
async def verify_domain(domain_id: str, authorization: str = Header(None)):
    """Trigger verification check for a domain."""
    await _auth(authorization)
    key = _get_resend_key()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.resend.com/domains/{domain_id}/verify",
            headers={"Authorization": f"Bearer {key}"}
        )
        if resp.status_code == 401:
            return {"error": "restricted_key", "message": "Need full-access key"}
        return resp.json()


@router.get("/dns-records")
async def get_dns_records(domain: str = "aurem.live", authorization: str = Header(None)):
    """
    Get the DNS records needed for email verification.
    Works even with a send-only key — returns the standard Resend DNS records.
    """
    await _auth(authorization)
    return {
        "domain": domain,
        "provider": "GoDaddy",
        "dns_records": _get_manual_dns_records(domain),
        "godaddy_instructions": _format_godaddy_guide(domain),
    }


def _get_manual_dns_records(domain: str):
    """Standard Resend DNS records for domain verification."""
    return [
        {
            "type": "MX",
            "name": f"send.{domain}" if domain == "aurem.live" else domain,
            "value": "feedback-smtp.us-east-1.amazonses.com",
            "priority": 10,
            "purpose": "Email sending via Resend/AWS SES",
        },
        {
            "type": "TXT",
            "name": f"send.{domain}" if domain == "aurem.live" else domain,
            "value": "v=spf1 include:amazonses.com ~all",
            "purpose": "SPF — Authorizes Resend to send emails on behalf of your domain",
        },
        {
            "type": "TXT",
            "name": f"resend._domainkey.{domain}",
            "value": "(Will be provided by Resend after domain registration — see step 2)",
            "purpose": "DKIM — Cryptographic signature to prevent email spoofing",
        },
        {
            "type": "TXT",
            "name": f"_dmarc.{domain}",
            "value": "v=DMARC1; p=none; rua=mailto:dmarc@aurem.live",
            "purpose": "DMARC — Email authentication policy (start with 'none', upgrade to 'quarantine' later)",
        },
    ]


def _format_godaddy_instructions(records, domain):
    """Format Resend DNS records as GoDaddy-specific steps."""
    steps = []
    for i, rec in enumerate(records, 1):
        rec_type = rec.get("type", rec.get("record_type", "TXT"))
        name = rec.get("name", "")
        value = rec.get("value", "")
        steps.append({
            "step": i,
            "type": rec_type,
            "name": name,
            "value": value,
            "godaddy_action": f"In GoDaddy DNS Manager → Add Record → Type: {rec_type} → Name: {name} → Value: {value}",
        })
    return steps


def _format_godaddy_guide(domain):
    """Complete GoDaddy DNS setup guide for Resend."""
    return {
        "title": f"GoDaddy DNS Setup for {domain}",
        "steps": [
            {
                "step": 1,
                "title": "Log into GoDaddy",
                "instruction": "Go to https://dcc.godaddy.com → My Products → Find aurem.live → DNS → Manage",
            },
            {
                "step": 2,
                "title": "Add SPF Record",
                "instruction": "Click 'Add New Record' → Type: TXT → Name: send → Value: v=spf1 include:amazonses.com ~all → TTL: 1 Hour → Save",
            },
            {
                "step": 3,
                "title": "Add MX Record",
                "instruction": "Click 'Add New Record' → Type: MX → Name: send → Value: feedback-smtp.us-east-1.amazonses.com → Priority: 10 → TTL: 1 Hour → Save",
            },
            {
                "step": 4,
                "title": "Add DMARC Record",
                "instruction": "Click 'Add New Record' → Type: TXT → Name: _dmarc → Value: v=DMARC1; p=none; rua=mailto:dmarc@aurem.live → TTL: 1 Hour → Save",
            },
            {
                "step": 5,
                "title": "Add DKIM Record (after Resend registration)",
                "instruction": "After registering the domain in Resend (step 6), Resend will give you a DKIM value. Add it as: Type: TXT → Name: resend._domainkey → Value: (from Resend) → TTL: 1 Hour → Save",
            },
            {
                "step": 6,
                "title": "Register Domain in Resend",
                "instruction": "Go to https://resend.com/domains → Add Domain → Enter 'aurem.live' → Copy the DKIM value and add it in step 5 → Click 'Verify DNS Records'",
            },
            {
                "step": 7,
                "title": "Verify",
                "instruction": "Wait 5-30 minutes for DNS propagation. Then click 'Verify' in Resend. Once verified, emails from ora@aurem.live will reach inboxes (not spam).",
            },
        ],
        "notes": [
            "DNS propagation can take up to 48 hours, but usually completes in 5-30 minutes",
            "Use 'send' subdomain (send.aurem.live) to keep main domain clean",
            "Start DMARC with p=none, upgrade to p=quarantine after 2 weeks of monitoring",
            "Your current Resend key is send-only. For domain management, create a full-access key at https://resend.com/api-keys",
        ],
    }



class SendFirstContactRequest(BaseModel):
    to_email: str
    to_name: str = "there"
    channel: str = "manual"


@router.post("/first-contact/send")
async def send_first_contact(req: SendFirstContactRequest, authorization: str = Header(None)):
    """Manually send a First Contact welcome email to a lead."""
    await _auth(authorization)
    from services.first_contact_email import send_first_contact_email
    result = await send_first_contact_email(req.to_email, req.to_name, req.channel)
    return result


@router.get("/first-contact/preview")
async def preview_first_contact(name: str = "Tejinder", authorization: str = Header(None)):
    """Preview the First Contact email template (returns raw HTML)."""
    await _auth(authorization)
    from services.first_contact_email import FIRST_CONTACT_HTML
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=FIRST_CONTACT_HTML.replace("{name}", name))
