"""
AUREM Client Dashboard API
===========================
Aggregated dashboard data for tenant clients (non-super-admin users).
Returns scan health, usage stats, pixel events, and AI context.
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone, timedelta
import logging
import jwt

router = APIRouter(prefix="/api/client", tags=["Client Dashboard"])

_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"

logger = logging.getLogger(__name__)


def set_db(database):
    global _db
    _db = database


def set_jwt(secret, algorithm="HS256"):
    global _jwt_secret, _jwt_algorithm
    _jwt_secret = secret
    _jwt_algorithm = algorithm


async def _get_user_from_token(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/dashboard")
async def get_client_dashboard(request: Request):
    """Get aggregated dashboard data for the logged-in tenant."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    payload = await _get_user_from_token(request)
    user_id = payload.get("user_id", "")
    tenant_id = payload.get("tenant_id", user_id)

    # Get user info
    user = await _db["users"].find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get workspace
    email = user.get("email", "")
    workspace = await _db["aurem_workspaces"].find_one(
        {"owner_email": email}, {"_id": 0}
    )

    # Get latest self-repair scan for this tenant
    ws_tenant = None
    if workspace:
        # Match by business_id or by website URL
        website = workspace.get("website", "")
        if website:
            ws_tenant = await _db["system_auto_repairs"].find_one(
                {"site_url": website}, {"_id": 0}, sort=[("scanned_at", -1)]
            )
        if not ws_tenant:
            ws_tenant = await _db["system_auto_repairs"].find_one(
                {"tenant_id": {"$regex": "reroots", "$options": "i"}},
                {"_id": 0},
                sort=[("scanned_at", -1)],
            )

    # Get scan history (last 10)
    scan_history = []
    if workspace:
        website = workspace.get("website", "")
        if website:
            cursor = _db["system_auto_repairs"].find(
                {"site_url": website}, {"_id": 0}
            ).sort("scanned_at", -1).limit(10)
            scan_history = await cursor.to_list(10)

    # Get usage stats
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = None
    if workspace:
        usage = await _db["aurem_usage"].find_one(
            {"business_id": workspace.get("business_id"), "billing_period": period},
            {"_id": 0},
        )

    # Get pixel events count (from webhooks/generic events)
    pixel_events_count = 0
    if workspace:
        try:
            pixel_events_count = await _db["pixel_events"].count_documents(
                {"business_id": workspace.get("business_id")}
            )
        except Exception as e:
            import logging
            logging.getLogger("aurem").debug(f"[ClientDash] pixel_events count error: {e}")

    # Get API key info
    api_key_info = None
    if workspace:
        key_doc = await _db["api_keys"].find_one(
            {"business_id": workspace.get("business_id")}, {"_id": 0}
        )
        if key_doc:
            api_key_info = {
                "key": key_doc.get("key", "")[:12] + "..." + key_doc.get("key", "")[-6:],
                "full_key": key_doc.get("key", ""),
                "is_active": key_doc.get("is_active", True),
                "permissions": key_doc.get("permissions", []),
            }

    # Build response
    health = None
    if ws_tenant:
        health = {
            "overall_score": ws_tenant.get("overall_score", 0),
            "scores": ws_tenant.get("scores", {}),
            "critical_count": ws_tenant.get("critical_count", 0),
            "warning_count": ws_tenant.get("warning_count", 0),
            "repairs_queued": len(ws_tenant.get("repairs", [])),
            "scanned_at": ws_tenant.get("scanned_at"),
        }

    return {
        "user": {
            "email": user.get("email"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "business_name": user.get("business_name") or (workspace.get("business_name") if workspace else ""),
        },
        "workspace": {
            "business_id": workspace.get("business_id") if workspace else None,
            "plan": workspace.get("plan") if workspace else None,
            "status": workspace.get("status") if workspace else None,
            "website": workspace.get("website") if workspace else None,
            "trial_override": workspace.get("trial_override", False) if workspace else False,
            "created_at": workspace.get("created_at") if workspace else None,
        } if workspace else None,
        "health": health,
        "scan_history": [
            {
                "overall_score": s.get("overall_score", 0),
                "scores": s.get("scores", {}),
                "critical_count": s.get("critical_count", 0),
                "warning_count": s.get("warning_count", 0),
                "repairs_queued": len(s.get("repairs", [])),
                "scanned_at": s.get("scanned_at"),
            }
            for s in scan_history
        ],
        "usage": {
            "ai_messages": usage.get("usage", {}).get("ai_messages", 0) if usage else 0,
            "gmail_messages": usage.get("usage", {}).get("gmail_messages", 0) if usage else 0,
            "whatsapp_messages": usage.get("usage", {}).get("whatsapp_messages", 0) if usage else 0,
            "phone_minutes": usage.get("usage", {}).get("phone_minutes", 0) if usage else 0,
            "actions_executed": usage.get("usage", {}).get("actions_executed", 0) if usage else 0,
            "included_messages": usage.get("included_messages", 0) if usage else 0,
            "billing_period": period,
        },
        "pixel_events": pixel_events_count,
        "api_key": api_key_info,
        "ai_context": workspace.get("ai_context", {}) if workspace else {},
    }


@router.post("/trigger-scan")
async def client_trigger_scan(request: Request):
    """Allow tenant client to manually trigger a scan of their own website."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    payload = await _get_user_from_token(request)
    user_id = payload.get("user_id", "")

    user = await _db["users"].find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    workspace = await _db["aurem_workspaces"].find_one(
        {"owner_email": user.get("email", "")}, {"_id": 0}
    )
    if not workspace or not workspace.get("website"):
        raise HTTPException(status_code=400, detail="No website configured for your workspace")

    from services.self_repair_loop import run_self_scan

    website = workspace["website"]
    biz_name = workspace.get("business_name", website)
    biz_id = workspace.get("business_id", "unknown")

    result = await run_self_scan(website, biz_id, biz_name)

    return {
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }


# ═══════════════════════════════════════════════════
# SCAN REPORT PDF DOWNLOAD
# ═══════════════════════════════════════════════════

@router.get("/scan-report-pdf")
async def scan_report_pdf(request: Request, scan_date: str = ""):
    """Generate a PDF scan report for a specific scan date."""
    from fastapi.responses import StreamingResponse
    import io

    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    payload = await _get_user_from_token(request)
    user_id = payload.get("user_id", "")

    user = await _db["users"].find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(404, "User not found")

    workspace = await _db["aurem_workspaces"].find_one(
        {"owner_email": user.get("email", "")}, {"_id": 0}
    )

    # Find the scan
    query = {}
    if workspace and workspace.get("website"):
        query["site_url"] = workspace["website"]
    if scan_date:
        query["scanned_at"] = {"$regex": scan_date[:10]}

    scan = await _db["system_auto_repairs"].find_one(
        query, {"_id": 0}, sort=[("scanned_at", -1)]
    )
    if not scan:
        raise HTTPException(404, "Scan not found")

    # Generate PDF
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('AuremTitle', parent=styles['Heading1'], fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1a1a1a'))
    sub_style = ParagraphStyle('AuremSub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#666666'), spaceAfter=16)
    heading_style = ParagraphStyle('AuremH2', parent=styles['Heading2'], fontSize=14, spaceBefore=16, spaceAfter=8, textColor=colors.HexColor('#333333'))
    body_style = ParagraphStyle('AuremBody', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#444444'), leading=14)

    elements = []

    # Header
    biz = workspace.get("business_name", scan.get("label", "")) if workspace else scan.get("label", "")
    site = scan.get("site_url", "")
    scanned = scan.get("scanned_at", "")[:19]

    elements.append(Paragraph("AUREM Scan Report", title_style))
    elements.append(Paragraph(f"{biz} — {site}", sub_style))
    elements.append(Paragraph(f"Scan Date: {scanned}", sub_style))
    elements.append(Spacer(1, 12))

    # Overall Score
    score = scan.get("overall_score", 0)
    score_color = '#22c55e' if score >= 80 else '#f59e0b' if score >= 60 else '#ef4444'
    elements.append(Paragraph(f"Overall Score: <font color='{score_color}'><b>{score}/100</b></font>", ParagraphStyle('ScoreStyle', parent=styles['Heading1'], fontSize=28, textColor=colors.HexColor('#1a1a1a'))))
    elements.append(Spacer(1, 8))

    # Category Breakdown
    elements.append(Paragraph("Category Breakdown", heading_style))
    scores = scan.get("scores", {})
    if scores:
        table_data = [["Category", "Score", "Rating"]]
        for cat, val in scores.items():
            rating = "Excellent" if val >= 80 else "Good" if val >= 60 else "Needs Work"
            table_data.append([cat.title(), str(val), rating])

        t = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e5e5')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 12))

    # Issues Summary
    elements.append(Paragraph("Issues Summary", heading_style))
    critical = scan.get("critical_count", 0)
    warnings = scan.get("warning_count", 0)
    total = scan.get("issues_total", 0)
    elements.append(Paragraph(f"Total Issues: {total} — Critical: {critical}, Warnings: {warnings}", body_style))
    elements.append(Spacer(1, 8))

    # Repairs
    repairs = scan.get("repairs", [])
    if repairs:
        elements.append(Paragraph(f"Repairs Queued: {len(repairs)}", heading_style))
        for r in repairs[:10]:
            desc = r.get("description", r.get("issue", "Repair item"))
            elements.append(Paragraph(f"• {desc}", body_style))
        elements.append(Spacer(1, 8))

    # Footer
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Generated by AUREM AI — aurem.live", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#999999'), alignment=1)))

    doc.build(elements)
    buf.seek(0)

    filename = f"aurem-scan-{site.replace('https://', '').replace('/', '_')}-{scanned[:10]}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
