"""
services/ora_skills_seed.py — iter 326hh-seed (Phase 3 P3.3).

Seeds the skills marketplace with five reference skills on first boot
so it isn't empty on day one. Idempotent — uses fixed skill_ids and
only inserts if the catalog is empty (or the specific skill_id is
missing). Safe to call on every startup.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Reference skills — written in plain English; the actual prompt/playbook
# content lives in `content.prompt`. The `manifest.tools` array advertises
# which ORA tools the skill expects to call.
SEED_SKILLS: list[dict[str, Any]] = [
    {
        "skill_id":    "aurem-gst-hst-filing",
        "name":        "GST/HST Filing Automation (Canada)",
        "description": (
            "Walks ORA through preparing a quarterly GST/HST return: "
            "pulls sales totals, applies the right rate per province, "
            "drafts the CRA-ready summary, and produces a one-page PDF "
            "for the founder to review and submit."
        ),
        "category":    "tax",
        "manifest":    {
            "tools": ["read_invoices", "summarize_sales", "generate_pdf"],
            "country": "CA",
        },
        "content":     {
            "prompt": (
                "You are filing a Canadian GST/HST return for the founder. "
                "Always confirm the province and reporting period BEFORE "
                "computing tax. Show the math step by step. Never submit "
                "to CRA — only prepare for founder review."
            ),
        },
        "pricing": {"model": "free"},
    },
    {
        "skill_id":    "aurem-wsib-compliance",
        "name":        "WSIB Compliance Checker (Ontario)",
        "description": (
            "Audits employee/contractor classifications, WSIB premium "
            "calculations, and overdue filings. Flags risks before an "
            "inspector does. Ontario-specific."
        ),
        "category":    "compliance",
        "manifest":    {
            "tools": ["read_payroll", "read_contracts", "policy_lookup"],
            "country": "CA", "province": "ON",
        },
        "content":     {
            "prompt": (
                "You audit WSIB compliance for an Ontario employer. Walk "
                "every active worker, classify them, compute the rate, "
                "and surface gaps. Always cite the WSIB rate schedule "
                "you used."
            ),
        },
        "pricing": {"model": "free"},
    },
    {
        "skill_id":    "aurem-gta-seasonal-campaigns",
        "name":        "GTA Seasonal Outreach Templates",
        "description": (
            "Pre-built SMS / email / voice templates for Greater Toronto "
            "Area service businesses by season (snow, AC tune-up, deck "
            "refinish, etc.). Drops straight into the blast engine."
        ),
        "category":    "marketing",
        "manifest":    {
            "tools": ["template_apply", "blast_queue_push"],
            "geography": "GTA",
        },
        "content":     {
            "prompt": (
                "Suggest the best seasonal outreach template for the "
                "current month and the lead's industry. If outside the "
                "GTA, decline and recommend the generic template pack."
            ),
        },
        "pricing": {"model": "free"},
    },
    {
        "skill_id":    "aurem-roofer-snow-clearing-pack",
        "name":        "Roofer — Snow & Ice Removal Outreach Pack",
        "description": (
            "Cold-weather upsell sequence for roofing contractors: "
            "ice-dam warnings, snow-load assessments, and gutter heat-"
            "cable upsells. Tuned for direct, no-nonsense tone."
        ),
        "category":    "outreach",
        "manifest":    {
            "tools": ["lead_score", "blast_queue_push"],
            "industry": "roofing",
        },
        "content":     {
            "prompt": (
                "You're writing for a roofing contractor reaching "
                "existing customers about snow/ice risk. Keep it direct, "
                "5-7 sentences, one clear CTA: book inspection."
            ),
        },
        "pricing": {"model": "free"},
    },
    {
        "skill_id":    "aurem-dental-recall-reminders",
        "name":        "Dental — Recall & Hygiene Reminders",
        "description": (
            "Warm, professional reminder sequence for dental practices: "
            "6-month hygiene recalls, treatment plan follow-ups, and "
            "missed-appointment recovery. Tuned for dental tone."
        ),
        "category":    "customer_success",
        "manifest":    {
            "tools": ["calendar_read", "blast_queue_push"],
            "industry": "dental",
        },
        "content":     {
            "prompt": (
                "You're writing for a dental clinic. Warm, professional, "
                "never pushy. Always mention insurance benefits expiring "
                "if relevant. End with a single, friendly CTA."
            ),
        },
        "pricing": {"model": "free"},
    },
]


async def ensure_seed_skills() -> dict:
    """Insert the 5 reference skills if they're not already present.
    Returns a small summary so callers can log activity."""
    try:
        from services.ora_skills import publish_skill, get_skill
    except Exception as e:
        return {"ok": False, "error": f"ora_skills import failed: {e}"}
    created = 0
    skipped = 0
    failed = 0
    for s in SEED_SKILLS:
        try:
            existing = await get_skill(s["skill_id"])
            if existing:
                skipped += 1
                continue
            r = await publish_skill(
                name=s["name"],
                description=s["description"],
                category=s["category"],
                author_email="seed@aurem.live",
                version="1.0.0",
                manifest=s.get("manifest"),
                content=s.get("content"),
                pricing=s.get("pricing"),
                skill_id=s["skill_id"],
            )
            if r.get("ok") and r.get("created"):
                created += 1
            elif r.get("ok"):
                skipped += 1
            else:
                failed += 1
                logger.warning(
                    f"[skills-seed] publish failed for {s['skill_id']}: "
                    f"{r.get('error')}"
                )
        except Exception as e:
            failed += 1
            logger.warning(f"[skills-seed] error on {s['skill_id']}: {e}")
    logger.info(
        f"[skills-seed] created={created} skipped={skipped} failed={failed}"
    )
    return {"ok": True, "created": created, "skipped": skipped,
            "failed": failed, "total": len(SEED_SKILLS)}
