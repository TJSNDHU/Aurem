"""Sales/Campaign — Template & Public-Facing Renderers.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pillars.sales.routes._shared import (
    _get_db, _verify_admin, _get_today_schedule,
    WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
)

router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])
logger = logging.getLogger(__name__)


@router.get("/competitor-templates")
async def get_competitor_templates(request: Request):
    """Get all competitor comparison campaign templates."""
    _verify_admin(request)
    return {
        "templates": {
            "whatsapp": list(COMPETITOR_TEMPLATES["whatsapp"].keys()),
            "email": COMPETITOR_TEMPLATES["email"]["switch_subject_lines"],
            "sms": list(COMPETITOR_TEMPLATES["sms"].keys()),
            "voice": list(COMPETITOR_TEMPLATES["voice"].keys()),
        },
        "positioning": "AUREM vs Traditional Agency — daily scanning, same-day fixes, AI outreach, $97/mo vs $500-2000/mo",
    }
# ══════════════════════════════════════════════
# Seed AUREM as Self-Client
# ══════════════════════════════════════════════
@router.post("/seed-aurem")
async def seed_aurem_client(request: Request):
    """Seed AUREM (Polaris Built Inc.) as self-client in tenant_customers."""
    _verify_admin(request)
    db = _get_db()
    if not db:
        raise HTTPException(500, "Database not initialized")

    existing = await db.tenant_customers.find_one({"business_id": "AURE-M001"})
    if existing:
        return {"success": True, "message": "AUREM self-client already exists", "tenant_id": existing.get("tenant_id")}

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "tenant_id": "polaris-built-001",
        "business_id": "AURE-M001",
        "full_name": "Pawandeep Singh Sandhu",
        "company_name": "Polaris Built Inc.",
        "company_address": {
            "street": "7221 Sigsbee Dr",
            "city": "Mississauga",
            "province": "Ontario",
            "postal_code": "L4T 3L6",
            "country": "Canada",
        },
        "website_url": "https://aurem.live",
        "email": "teji.ss1986@gmail.com",
        "phone": "+12265017777",
        "whatsapp": "+12265017777",
        "industry": "AI Technology",
        "category": "SaaS Platform",
        "sub_category": "Autonomous Business AI",
        "business_description": (
            "AUREM is an autonomous AI platform that runs businesses automatically. "
            "Lead scoring, invoice automation, website repair, morning brief, economic intelligence."
        ),
        "products": [
            {
                "name": "Starter Plan",
                "price_cad": 97,
                "billing": "monthly",
                "features": [
                    "500 AI actions/month", "Lead scoring + follow-up",
                    "Invoice automation", "Morning Brief",
                    "Website repair", "ORA chat assistant",
                ],
            },
            {
                "name": "Growth Plan",
                "price_cad": 297,
                "billing": "monthly",
                "features": [
                    "5000 AI actions/month", "ORA voice AI",
                    "Economic Intelligence", "3 workspaces",
                    "Partner referral access",
                ],
            },
            {
                "name": "Enterprise Plan",
                "price_cad": 997,
                "billing": "monthly",
                "features": [
                    "Unlimited actions", "White-label",
                    "25 concurrent voice", "Dedicated onboarding",
                ],
            },
        ],
        "target_market": {
            "location": "Mississauga, Ontario, Canada",
            "business_types": TARGET_CATEGORIES,
            "ideal_client": {
                "revenue_range": "$100K-$2M CAD/year",
                "employees": "1-20",
                "pain_points": [
                    "No time for follow-ups", "Missing leads",
                    "Website not ranking", "Manual invoice collection",
                    "No marketing automation",
                ],
            },
        },
        "plan": "enterprise",
        "plan_price_cad": 997,
        "plan_started": now,
        "plan_status": "active",
        "is_self_client": True,
        "billing_cycle": "monthly",
        "campaign": {
            "active": True,
            "daily_call_limit": 50,
            "daily_email_limit": 100,
            "daily_whatsapp_limit": 50,
            "calling_hours_start": "09:00",
            "calling_hours_end": "17:00",
            "timezone": "America/Toronto",
            "call_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "language": "en-CA",
        },
        "usage": {
            "actions_limit": 999999,
            "actions_used": 0,
            "actions_remaining": 999999,
            "pipeline_runs_today": 0,
            "pipeline_runs_limit": 999,
            "last_reset_date": now,
            "reset_cycle": "daily",
        },
        "performance": {
            "website_score": 0,
            "last_scan_date": None,
            "total_scans": 0,
            "leads_found": 0,
            "leads_converted": 0,
            "invoices_sent": 0,
            "invoices_paid": 0,
            "revenue_tracked": 0,
            "automations_run": 0,
            "issues_fixed": 0,
        },
        "joined_date": now,
        "last_active": now,
        "created_by": "system",
        "notes": "AUREM self-client — dogfooding the platform",
        "is_active": True,
    }
    await db.tenant_customers.insert_one(doc)

    # Also create the campaign record
    await db.campaigns.update_one(
        {"campaign_id": "aurem-acquisition-001"},
        {"$setOnInsert": {
            "campaign_id": "aurem-acquisition-001",
            "name": "AUREM Acquisition Campaign",
            "tenant_id": "polaris-built-001",
            "status": "active",
            "type": "outbound",
            "target_location": "Mississauga, Ontario, Canada",
            "target_categories": TARGET_CATEGORIES,
            "daily_call_limit": 50,
            "daily_email_limit": 100,
            "daily_whatsapp_limit": 50,
            "calling_hours": {"start": "09:00", "end": "17:00"},
            "timezone": "America/Toronto",
            "call_days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
            "language": "en-CA",
            "created_at": now,
            "stats": {
                "leads_scraped": 0,
                "websites_scanned": 0,
                "calls_made": 0,
                "emails_sent": 0,
                "whatsapp_sent": 0,
                "calls_answered": 0,
                "email_opens": 0,
                "replies_received": 0,
                "reports_sent": 0,
                "demo_requests": 0,
                "signups": 0,
                "revenue_cad": 0,
            },
        }},
        upsert=True,
    )

    return {"success": True, "tenant_id": "polaris-built-001", "business_id": "AURE-M001"}
@router.get("/leads/{lead_id}/templates/preview")
async def preview_lead_templates(lead_id: str, request: Request):
    """
    Preview all 4 rendered AUREM outreach templates for a lead (without sending).
    Returns: {variables, whatsapp, sms, email: {subject, html}, voice_script}.
    """
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    from services.aurem_outreach_templates import render_all
    return render_all(lead)


