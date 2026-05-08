"""
AUREM Case Study Router — Dual Mode (Admin + Customer)
═══════════════════════════════════════════════════════════════════════════════
  Customer (JWT self-serve):
    POST /api/case-study/preview       — JSON preview of own data
    POST /api/case-study/generate      — build PDF for own account
    GET  /api/case-study/mine          — list past reports
    GET  /api/case-study/download/{id} — stream PDF (owner-only)

  Admin (super_admin JWT):
    POST /api/admin/case-study/preview  — JSON preview for any tenant
    POST /api/admin/case-study/generate — build PDF for any tenant
    POST /api/admin/case-study/email    — email the PDF to the customer
    GET  /api/admin/case-study/list     — all reports (paginated)
"""
import os
import base64
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Case Study"])

_db = None


def set_db(database):
    global _db
    _db = database


# ═════════════════════════════════════════════════════════════════════
# Auth helpers
# ═════════════════════════════════════════════════════════════════════
def _decode(request: Request) -> dict:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(token, os.environ.get("JWT_SECRET", ""), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _require_user(request: Request) -> dict:
    p = _decode(request)
    email = (p.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "No email on token")
    if _db is None:
        raise HTTPException(503, "db not ready")
    u = await _db.platform_users.find_one({"email": email}, {"_id": 0})
    if not u:
        raise HTTPException(403, "Platform user not found")
    return {"email": email, "bin": u.get("bin"), "name": u.get("business_name") or u.get("name") or email, "role": p.get("role")}


async def _require_admin(request: Request) -> dict:
    p = _decode(request)
    role = (p.get("role") or "").lower()
    if role not in ("admin", "super_admin") and not (p.get("is_admin") or p.get("is_super_admin")):
        raise HTTPException(403, "Admin required")
    return p


# ═════════════════════════════════════════════════════════════════════
# Period resolver
# ═════════════════════════════════════════════════════════════════════
def _resolve_period(report_type: str, start: Optional[str], end: Optional[str]):
    now = datetime.now(timezone.utc)
    if report_type == "monthly":
        period_end = now
        period_start = now - timedelta(days=30)
    elif report_type == "quarterly":
        period_end = now
        period_start = now - timedelta(days=90)
    elif report_type == "custom":
        if not (start and end):
            raise HTTPException(400, "custom requires period_start and period_end")
        try:
            period_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            period_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(400, "invalid date format — use ISO 8601")
        if period_end <= period_start:
            raise HTTPException(400, "period_end must be after period_start")
    else:
        raise HTTPException(400, f"invalid report_type: {report_type}")
    return period_start, period_end


class GenerateBody(BaseModel):
    report_type: str = Field("monthly", pattern="^(monthly|quarterly|custom)$")
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    # Admin-only
    target_email: Optional[str] = None
    target_bin: Optional[str] = None
    target_name: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════
# Customer self-serve
# ═════════════════════════════════════════════════════════════════════
@router.post("/api/case-study/preview")
async def customer_preview(body: GenerateBody, request: Request):
    user = await _require_user(request)
    from services.case_study_builder import aggregate_report_data
    start, end = _resolve_period(body.report_type, body.period_start, body.period_end)
    payload = await aggregate_report_data(
        _db,
        customer_email=user["email"],
        customer_bin=user.get("bin"),
        customer_name=user["name"],
        period_start=start,
        period_end=end,
        report_type=body.report_type,
    )
    return {"ok": True, "preview": payload}


@router.post("/api/case-study/generate")
async def customer_generate(body: GenerateBody, request: Request):
    user = await _require_user(request)
    from services.case_study_builder import aggregate_report_data
    from services.case_study_pdf import build_and_write_pdf
    start, end = _resolve_period(body.report_type, body.period_start, body.period_end)
    payload = await aggregate_report_data(
        _db,
        customer_email=user["email"],
        customer_bin=user.get("bin"),
        customer_name=user["name"],
        period_start=start,
        period_end=end,
        report_type=body.report_type,
    )
    rec = await build_and_write_pdf(_db, payload)
    return {
        "ok": True,
        "report_id": rec["report_id"],
        "download_url": f"/api/case-study/download/{rec['report_id']}",
        "summary": rec["metadata"],
        "outlook_preview": rec["outlook_preview"],
    }


@router.get("/api/case-study/mine")
async def customer_list(request: Request, limit: int = Query(20, ge=1, le=100)):
    user = await _require_user(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    out = []
    async for d in _db.case_study_reports.find(
        {"customer_email": user["email"]}, {"_id": 0}
    ).sort("issued_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "reports": out}


@router.get("/api/case-study/download/{report_id}")
async def download(report_id: str, request: Request):
    """Stream the PDF. Owner or admin only."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    rec = await _db.case_study_reports.find_one({"report_id": report_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "report not found")
    # Auth: try user first, then admin
    try:
        user = await _require_user(request)
        if rec.get("customer_email") != user["email"]:
            # fall through to admin check
            await _require_admin(request)
    except HTTPException:
        await _require_admin(request)

    from services.case_study_pdf import OUTPUT_DIR
    path = OUTPUT_DIR / rec["pdf_filename"]
    if not path.exists():
        raise HTTPException(410, "PDF file no longer on disk — please regenerate")
    return FileResponse(
        path=str(path),
        filename=rec["pdf_filename"],
        media_type="application/pdf",
    )


# ═════════════════════════════════════════════════════════════════════
# Admin
# ═════════════════════════════════════════════════════════════════════
async def _resolve_target(body: GenerateBody):
    if not (body.target_email or body.target_bin):
        raise HTTPException(400, "target_email or target_bin required")
    q = {}
    if body.target_email:
        q["email"] = body.target_email.lower()
    elif body.target_bin:
        q["bin"] = body.target_bin
    u = await _db.platform_users.find_one(q, {"_id": 0})
    if not u:
        raise HTTPException(404, f"target not found: {q}")
    return {
        "email": u.get("email") or "",
        "bin": u.get("bin"),
        "name": body.target_name or u.get("business_name") or u.get("name") or (u.get("email") or "").split("@")[0] or "Customer",
    }


@router.post("/api/admin/case-study/preview")
async def admin_preview(body: GenerateBody, request: Request):
    await _require_admin(request)
    tgt = await _resolve_target(body)
    from services.case_study_builder import aggregate_report_data
    start, end = _resolve_period(body.report_type, body.period_start, body.period_end)
    payload = await aggregate_report_data(
        _db,
        customer_email=tgt["email"],
        customer_bin=tgt["bin"],
        customer_name=tgt["name"],
        period_start=start,
        period_end=end,
        report_type=body.report_type,
    )
    return {"ok": True, "preview": payload}


@router.post("/api/admin/case-study/generate")
async def admin_generate(body: GenerateBody, request: Request):
    await _require_admin(request)
    tgt = await _resolve_target(body)
    from services.case_study_builder import aggregate_report_data
    from services.case_study_pdf import build_and_write_pdf
    start, end = _resolve_period(body.report_type, body.period_start, body.period_end)
    payload = await aggregate_report_data(
        _db,
        customer_email=tgt["email"],
        customer_bin=tgt["bin"],
        customer_name=tgt["name"],
        period_start=start,
        period_end=end,
        report_type=body.report_type,
    )
    rec = await build_and_write_pdf(_db, payload)
    return {
        "ok": True,
        "report_id": rec["report_id"],
        "target": tgt,
        "download_url": f"/api/case-study/download/{rec['report_id']}",
        "summary": rec["metadata"],
        "outlook_preview": rec["outlook_preview"],
    }


class EmailBody(BaseModel):
    report_id: str
    to_email: Optional[str] = None
    subject: Optional[str] = None
    message_html: Optional[str] = None


@router.post("/api/admin/case-study/email")
async def admin_email(body: EmailBody, request: Request):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    rec = await _db.case_study_reports.find_one({"report_id": body.report_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "report not found")
    from services.case_study_pdf import OUTPUT_DIR
    path = OUTPUT_DIR / rec["pdf_filename"]
    if not path.exists():
        raise HTTPException(410, "PDF file no longer on disk — please regenerate")

    to = (body.to_email or rec.get("customer_email") or "").lower()
    if not to:
        raise HTTPException(400, "no recipient")

    subject = body.subject or f"Your AUREM Business Review — {rec.get('period_end','')}"
    msg_html = body.message_html or (
        f"<p>Hello {rec.get('customer_name','')},</p>"
        f"<p>Attached is your AUREM Business Review for {rec.get('period_start','')} — {rec.get('period_end','')}.</p>"
        f"<p>Headline metrics: <strong>{rec['metadata']['uptime_pct']}% uptime</strong>, "
        f"<strong>{rec['metadata']['hours_saved']}h saved</strong>, "
        f"<strong>${rec['metadata']['dollars_saved']}</strong> in avoided cost.</p>"
        f"<p>If you'd like to review in a live session, reply to this email — ORA will schedule.</p>"
        f"<p style='color:#888;font-size:12px;'>— AUREM Autonomous Systems</p>"
    )

    # Send via Resend with attachment
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY") or ""
        if not resend.api_key:
            raise RuntimeError("RESEND_API_KEY missing")
        with open(path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("ascii")
        from_email = os.environ.get("RESEND_FROM_EMAIL") or "ORA <ora@aurem.live>"
        sent = resend.Emails.send({
            "from": from_email,
            "to": [to],
            "subject": subject,
            "html": msg_html,
            "attachments": [{
                "filename": rec["pdf_filename"],
                "content": pdf_b64,
            }],
        })
        await _db.case_study_reports.update_one(
            {"report_id": body.report_id},
            {"$set": {"emailed_at": datetime.now(timezone.utc).isoformat(), "emailed_to": to}},
        )
        return {"ok": True, "resend_id": (sent or {}).get("id"), "to": to}
    except Exception as e:
        logger.exception(f"[case-study] email failed: {e}")
        raise HTTPException(500, f"email failed: {e}")


@router.get("/api/admin/case-study/list")
async def admin_list(request: Request, limit: int = Query(50, ge=1, le=500)):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    out = []
    async for d in _db.case_study_reports.find({}, {"_id": 0}).sort("issued_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "reports": out}


@router.get("/api/admin/case-study/tenants")
async def admin_tenants(request: Request, q: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
    """Quick tenant picker for admin UI — returns platform_users list."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    query = {}
    if q:
        rgx = {"$regex": q, "$options": "i"}
        query = {"$or": [{"email": rgx}, {"business_name": rgx}, {"bin": rgx}]}
    out = []
    async for u in _db.platform_users.find(
        query,
        {"_id": 0, "email": 1, "bin": 1, "business_name": 1, "name": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit):
        out.append({
            "email": u.get("email"),
            "bin": u.get("bin"),
            "name": u.get("business_name") or u.get("name") or (u.get("email") or "").split("@")[0],
        })
    return {"ok": True, "count": len(out), "tenants": out}


# ═════════════════════════════════════════════════════════════════════
# SYSTEM AUDIT — "The Heartbeat of AUREM"
# Admin-only. Generates a 10-page platform self-audit PDF from live
# codebase + config. Optionally emails it out via Resend.
# ═════════════════════════════════════════════════════════════════════
class SystemAuditEmailBody(BaseModel):
    to_email: Optional[str] = None
    subject: Optional[str] = None


@router.post("/api/admin/case-study/system-audit")
async def admin_generate_system_audit(request: Request):
    """One-click generate a fresh System Architecture Report PDF."""
    await _require_admin(request)
    from services.project_report_builder import build_project_report_pdf
    res = await build_project_report_pdf(db=_db)
    return {
        "ok": True,
        "report_id": res["report_id"],
        "pdf_size_bytes": res["pdf_size_bytes"],
        "download_url": f"/api/admin/case-study/system-audit/download/{res['report_id']}",
        "summary": res["summary"],
    }


@router.get("/api/admin/case-study/system-audit/download/{report_id}")
async def admin_download_system_audit(report_id: str, request: Request):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    rec = await _db.system_audit_reports.find_one({"report_id": report_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "audit report not found")
    from services.case_study_pdf import OUTPUT_DIR
    path = OUTPUT_DIR / rec["pdf_filename"]
    if not path.exists():
        raise HTTPException(410, "PDF file no longer on disk — please regenerate")
    return FileResponse(
        path=str(path),
        filename=rec["pdf_filename"],
        media_type="application/pdf",
    )


@router.get("/api/admin/case-study/system-audit/list")
async def admin_list_system_audits(request: Request, limit: int = Query(30, ge=1, le=200)):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    out = []
    async for d in _db.system_audit_reports.find({}, {"_id": 0}).sort("issued_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "reports": out}


@router.post("/api/admin/case-study/system-audit/email")
async def admin_email_system_audit(body: SystemAuditEmailBody, request: Request):
    """Generate fresh PDF + email it as the monthly Heartbeat."""
    payload = await _require_admin(request)
    from services.project_report_builder import build_project_report_pdf, email_system_audit_pdf
    res = await build_project_report_pdf(db=_db)
    to_email = (body.to_email
                or payload.get("email")
                or os.environ.get("SYSTEM_AUDIT_RECIPIENT")
                or os.environ.get("ADMIN_ALERT_EMAIL"))
    if not to_email:
        raise HTTPException(400, "no recipient — provide to_email or set SYSTEM_AUDIT_RECIPIENT env")
    em = await email_system_audit_pdf(
        pdf_path=res["pdf_path"],
        report_id=res["report_id"],
        summary=res["summary"],
        to_email=to_email,
        subject=body.subject,
    )
    if _db is not None:
        await _db.system_audit_reports.update_one(
            {"report_id": res["report_id"]},
            {"$set": {
                "manual_emailed_at": datetime.now(timezone.utc).isoformat(),
                "manual_email_to": to_email,
                "manual_emailed": em.get("ok"),
            }},
        )
    return {
        "ok": bool(em.get("ok")),
        "report_id": res["report_id"],
        "to": to_email,
        "resend_id": em.get("resend_id"),
        "error": em.get("error"),
    }
