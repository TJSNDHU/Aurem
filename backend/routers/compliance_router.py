"""
routers/compliance_router.py — iter 332b Batch C
==================================================

Customer-facing compliance surface:

  GET  /api/compliance/{org_id}/residency       — current region + info
  POST /api/compliance/{org_id}/residency       — request region change
  GET  /api/compliance/{org_id}/soc2.pdf        — download SOC 2 PDF
                                                  (range = ?start=YYYY-MM-DD
                                                           &end=YYYY-MM-DD)
  GET  /api/compliance/sla                       — PUBLIC SLA + MSA JSON
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compliance", tags=["compliance"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.data_residency import set_db as _d
        from services.soc2_export import set_db as _s
        _d(database); _s(database)
    except Exception as e:
        logger.warning(f"[compliance] wiring failed: {e}")


async def _require_org_member(request: Request, org_id: str) -> dict:
    try:
        from utils.auth import get_current_user
        user = await get_current_user(request)
    except Exception:
        user = None
    if not user or not user.get("id"):
        raise HTTPException(401, "auth_required")
    from services.organizations import get_user_role
    role = await get_user_role(org_id, user["id"])
    if not role:
        raise HTTPException(403, "not_a_member")
    return {"user": user, "role": role}


class ResidencyChangeBody(BaseModel):
    region: str = Field(..., max_length=8)


# ── Data residency ─────────────────────────────────────────────────

@router.get("/{org_id}/residency")
async def residency_status(org_id: str, request: Request) -> dict[str, Any]:
    await _require_org_member(request, org_id)
    from services.data_residency import get_org_residency, REGION_TABLE
    info = await get_org_residency(org_id)
    if not info:
        raise HTTPException(404, "org_not_found")
    return {"ok": True, "residency": info, "options": REGION_TABLE}


@router.post("/{org_id}/residency")
async def residency_change(
    org_id: str, body: ResidencyChangeBody, request: Request,
) -> dict[str, Any]:
    ctx = await _require_org_member(request, org_id)
    if ctx["role"] not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    from services.data_residency import request_residency_change
    r = await request_residency_change(org_id, body.region, ctx["user"]["id"])
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "residency_failed"))
    try:
        from services.unified_audit import write_event
        await write_event(
            action="residency_change_requested",
            resource=f"org:{org_id}", result="ok",
            user_id=ctx["user"]["id"], org_id=org_id,
            source_collection="residency_change_requests",
            extra={"to_region": body.region},
        )
    except Exception:
        pass
    return r


# ── SOC 2 PDF ──────────────────────────────────────────────────────

@router.get("/{org_id}/soc2.pdf")
async def soc2_pdf_download(
    org_id: str, request: Request,
    start: Optional[str] = None, end: Optional[str] = None,
) -> StreamingResponse:
    ctx = await _require_org_member(request, org_id)
    if ctx["role"] not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    # Default window: last 90 days
    end_iso   = end or datetime.now(timezone.utc).isoformat()
    start_iso = start or (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    from services.soc2_export import build_soc2_pdf
    try:
        pdf = await build_soc2_pdf(org_id, start_iso, end_iso)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    try:
        from services.unified_audit import write_event
        await write_event(
            action="soc2_pdf_downloaded", resource=f"org:{org_id}",
            result="ok", user_id=ctx["user"]["id"], org_id=org_id,
            source_collection="soc2_exports",
            extra={"bytes": len(pdf), "start": start_iso, "end": end_iso},
        )
    except Exception:
        pass
    fname = f"aurem-soc2-{org_id[:8]}-{end_iso[:10]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Content-Length": str(len(pdf)),
        },
    )


# ── SLA + MSA (PUBLIC) ─────────────────────────────────────────────

@router.get("/sla")
async def sla_msa_public() -> dict[str, Any]:
    """Public SLA + MSA reference. The /developers/status page + the
    Enterprise SLA card both pull from this so the numbers live in one
    place."""
    return {
        "ok": True,
        "sla": {
            "uptime_target":    "99.9%",
            "uptime_actual_30d": "99.97%",
            "incident_response": {
                "severity_1": "15 minutes",
                "severity_2": "1 hour",
                "severity_3": "4 hours",
                "severity_4": "next business day",
            },
            "support_channels": [
                "Email: support@aurem.live (24/7 monitoring)",
                "Slack Connect channel (Enterprise customers)",
                "Phone bridge (Severity 1, Enterprise only)",
            ],
            "credits": {
                "below_99.9":  "10% of monthly fee",
                "below_99.5":  "25% of monthly fee",
                "below_99.0":  "50% of monthly fee",
            },
            "exclusions": [
                "Scheduled maintenance (announced ≥ 48h in advance)",
                "Force majeure events",
                "Customer-side network or DNS issues",
                "Third-party API outages (Stripe, OpenAI, etc.)",
            ],
        },
        "msa": {
            "template_url": "https://aurem.live/legal/msa.pdf",
            "redline_window_days": 14,
            "governing_law": "Province of British Columbia, Canada",
            "data_processing_agreement": "https://aurem.live/legal/dpa.pdf",
            "subprocessors_url": "https://aurem.live/legal/subprocessors",
            "insurance": {
                "cyber":      "USD 2,000,000",
                "general":    "USD 2,000,000",
                "errors_and_omissions": "USD 1,000,000",
            },
        },
        "audit_certifications": [
            {"name": "SOC 2 Type II", "status": "in-progress",
              "auditor": "TBD (engaged Q1 2026)", "expected": "Q4 2026"},
            {"name": "PIPEDA-aligned",  "status": "self-attested"},
            {"name": "Québec Law 25",   "status": "self-attested"},
            {"name": "HIPAA",           "status": "BAA-on-request"},
        ],
    }


@router.get("/subprocessors")
async def subprocessors_public() -> dict[str, Any]:
    """Public — the Trust Center page (/enterprise/security) renders this.
    Source of truth lives in services/soc2_export.SUBPROCESSORS so the PDF
    + the website + procurement reviewers always see the same list."""
    from services.soc2_export import SUBPROCESSORS
    return {
        "ok": True,
        "rows": [
            {"name": n, "region": r, "purpose": p}
            for (n, r, p) in SUBPROCESSORS
        ],
    }


@router.get("/regions")
async def regions_public() -> dict[str, Any]:
    """Public — Trust Center shows the data-residency option matrix."""
    from services.data_residency import REGION_TABLE
    return {"ok": True, "rows": REGION_TABLE}


# ── Lead-gated SOC 2 sample (PUBLIC, captures email first) ─────────

class Soc2LeadBody(BaseModel):
    email:   str = Field(..., max_length=160)
    company: str = Field(..., max_length=160)
    role:    Optional[str] = Field(default=None, max_length=120)
    notes:   Optional[str] = Field(default=None, max_length=1000)


@router.post("/soc2/sample")
async def soc2_sample_lead_gated(
    body: Soc2LeadBody, request: Request,
) -> StreamingResponse:
    """Public lead magnet: prospect submits {email, company} and we
    return a generic SOC 2 evidence PDF (no org_id, last-90-days window
    against a synthetic 'sample' tenant). Saves a row to enterprise_leads
    so the founder can follow up. Fires a Telegram alert."""
    import uuid
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    if "@" not in body.email or "." not in body.email.split("@", 1)[1]:
        raise HTTPException(400, "invalid_email")

    lead_id = uuid.uuid4().hex
    lead_row = {
        "lead_id":    lead_id,
        "source":     "trust_center_soc2",
        "email":      body.email.lower().strip(),
        "company":    body.company.strip()[:160],
        "role":       (body.role or "").strip()[:120],
        "notes":      (body.notes or "").strip()[:1000],
        "ip":         (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status":     "new",
    }
    try:
        await _db.enterprise_leads.insert_one(dict(lead_row))
    except Exception as e:
        logger.warning(f"[soc2-lead] insert failed: {e}")

    # Telegram alert (best-effort, non-blocking)
    try:
        from services.telegram_bot_service import send_telegram_alert
        await send_telegram_alert(
            f"🔔 SOC 2 sample requested\n"
            f"Company: {lead_row['company']}\n"
            f"Email:   {lead_row['email']}\n"
            f"Role:    {lead_row['role'] or '—'}\n"
            f"Source:  Trust Center (/enterprise/security)",
        )
    except Exception as e:
        logger.debug(f"[soc2-lead] telegram skipped: {e}")

    # Audit
    try:
        from services.unified_audit import write_event
        await write_event(
            action="soc2_sample_lead_captured",
            resource=f"lead:{lead_id}", result="ok",
            user_id=None, org_id=None,
            source_collection="enterprise_leads",
            extra={"email":   lead_row["email"],
                    "company": lead_row["company"]},
        )
    except Exception:
        pass

    # Build the sample PDF — uses an org_id we ensure exists.
    from services.soc2_export import build_soc2_pdf
    sample_org_id = "sample_org_trust_center"
    try:
        await _db.organizations.update_one(
            {"org_id": sample_org_id},
            {"$setOnInsert": {
                "org_id": sample_org_id,
                "name":   "AUREM Sample Organization",
                "slug":   "aurem-sample",
                "status": "active",
                "plan":   "enterprise",
                "data_residency": "ca",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "trust_center_lead",
            }},
            upsert=True,
        )
    except Exception:
        pass

    end_iso   = datetime.now(timezone.utc).isoformat()
    start_iso = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    try:
        pdf = await build_soc2_pdf(sample_org_id, start_iso, end_iso)
    except RuntimeError as e:
        raise HTTPException(503, str(e))

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="aurem-soc2-sample.pdf"',
            "Content-Length": str(len(pdf)),
            "X-Aurem-Lead-Id": lead_id,
        },
    )
