"""
Monthly PDF Report Engine — P1 #4
==================================
Auto-generates a customer's monthly report PDF and uploads to storage + sends
via WhatsApp + Email.

Entry points:
    generate_for_user(email)          -- one-off on demand
    monthly_report_cron()              -- run on 1st of month, iterates all active tenants

Uses reportlab (already installed).
Output path: /app/backend/static/reports/{bin}_{YYYY-MM}.pdf
Served at: /api/static/reports/...  (mounted via server.py static)
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent / "static" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_db = None


def set_db(db):
    global _db
    _db = db


def _safe(v, default=0):
    try:
        return v if v is not None else default
    except Exception:
        return default


async def _gather_metrics(db, email: str, month_start: datetime, month_end: datetime) -> Dict:
    """Pull metrics for the reporting window."""
    email = email.lower()
    iso_start, iso_end = month_start.isoformat(), month_end.isoformat()

    # Reviews
    new_reviews = await db.google_reviews.count_documents({
        "email": email, "date": {"$gte": iso_start, "$lt": iso_end}
    })
    ws = await db.aurem_workspaces.find_one({"owner_email": email}, {"_id": 0, "google_rating": 1, "google_total_reviews": 1, "website": 1}) or {}
    rating = float(ws.get("google_rating") or 0)

    # Website score (latest scan)
    site_url = ws.get("website", "")
    latest_scan = None
    if site_url:
        latest_scan = await db.system_auto_repairs.find_one(
            {"site_url": site_url}, {"_id": 0, "overall_score": 1, "scanned_at": 1}, sort=[("scanned_at", -1)]
        )
    site_score = int((latest_scan or {}).get("overall_score", 0))

    # Fixes applied in window
    fixes_applied = 0
    if site_url:
        cur = db.system_auto_repairs.find(
            {"site_url": site_url, "scanned_at": {"$gte": iso_start, "$lt": iso_end}},
            {"_id": 0, "repairs": 1}
        )
        async for r in cur:
            fixes_applied += sum(1 for rp in (r.get("repairs") or []) if rp.get("status") == "completed")

    # Calls (Twilio logs)
    calls = await db.twilio_call_logs.count_documents({
        "tenant_email": email, "started_at": {"$gte": iso_start, "$lt": iso_end}
    }) if "twilio_call_logs" in await db.list_collection_names() else 0

    # Leads
    leads = await db.campaign_leads.count_documents({
        "tenant_email": email, "created_at": {"$gte": iso_start, "$lt": iso_end}
    })

    return {
        "new_reviews": new_reviews,
        "rating": rating,
        "site_score": site_score,
        "fixes_applied": fixes_applied,
        "calls": calls,
        "leads": leads,
        "site_url": site_url,
    }


def _render_pdf(pdf_path: Path, *, business_name: str, bin_id: str, month_label: str, metrics: Dict):
    """Render a minimalist monthly report PDF using reportlab."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import inch

    styles = getSampleStyleSheet()
    gold = colors.HexColor("#C9A84C")
    ink = colors.HexColor("#1A1A1A")

    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=ink, fontSize=24, leading=28, alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=gold, fontSize=11, leading=14, alignment=0, spaceBefore=12)
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=ink, fontSize=10, leading=14)
    muted = ParagraphStyle("muted", parent=body, textColor=colors.HexColor("#666666"), fontSize=9)

    doc = SimpleDocTemplate(str(pdf_path), pagesize=LETTER, topMargin=0.6*inch, bottomMargin=0.6*inch, leftMargin=0.7*inch, rightMargin=0.7*inch)
    flow = []

    flow.append(Paragraph("AUREM Monthly Report", h1))
    flow.append(Paragraph(f"<b>{business_name}</b> &nbsp;·&nbsp; BIN <font color='#C9A84C'>{bin_id}</font> &nbsp;·&nbsp; {month_label}", muted))
    flow.append(Spacer(1, 18))

    # Metrics table
    data = [
        ["METRIC", "THIS MONTH"],
        ["New Reviews", str(metrics.get("new_reviews", 0))],
        ["Google Rating", f"{metrics.get('rating', 0):.1f} / 5"],
        ["Website Score", f"{metrics.get('site_score', 0)} / 100"],
        ["Auto-fixes Applied", str(metrics.get("fixes_applied", 0))],
        ["Calls Received", str(metrics.get("calls", 0))],
        ["New Leads", str(metrics.get("leads", 0))],
    ]
    t = Table(data, colWidths=[3.2*inch, 2.2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), gold),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TEXTCOLOR", (0, 1), (-1, -1), ink),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF6")]),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, gold),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, gold),
    ]))
    flow.append(t)

    flow.append(Spacer(1, 18))
    flow.append(Paragraph("What AUREM Did For You", h2))
    did_items = []
    if metrics.get("fixes_applied", 0) > 0:
        did_items.append(f"Applied <b>{metrics['fixes_applied']}</b> automated website fixes (SEO, meta tags, schema).")
    if metrics.get("new_reviews", 0) > 0:
        did_items.append(f"Tracked <b>{metrics['new_reviews']}</b> new Google reviews this month.")
    if metrics.get("calls", 0) > 0:
        did_items.append(f"Captured <b>{metrics['calls']}</b> inbound calls via your AI receptionist.")
    if metrics.get("leads", 0) > 0:
        did_items.append(f"Surfaced <b>{metrics['leads']}</b> new leads into your pipeline.")
    if not did_items:
        did_items.append("Your agents are calibrating — next month's report will show richer activity as they warm up.")
    for s in did_items:
        flow.append(Paragraph(f"• {s}", body))

    flow.append(Spacer(1, 24))
    flow.append(Paragraph("— AUREM AI  ·  aurem.live", muted))

    doc.build(flow)


async def generate_for_user(email: str, month: Optional[str] = None) -> Optional[Dict]:
    """Render PDF for one user. Returns dict with url + metrics, or None on failure."""
    if _db is None:
        logger.warning("[REPORT] DB not set")
        return None
    email = email.lower()

    user = await _db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await _db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        return None

    now = datetime.now(timezone.utc)
    # Default: previous month
    if month:
        year, mo = map(int, month.split("-"))
        month_start = datetime(year, mo, 1, tzinfo=timezone.utc)
    else:
        # Previous full month
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start = (first_of_month - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    next_month = (month_start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_label = month_start.strftime("%B %Y")
    month_key = month_start.strftime("%Y-%m")

    metrics = await _gather_metrics(_db, email, month_start, next_month)

    bin_id = user.get("business_id", "BIN")
    business_name = user.get("company_name") or user.get("business_name") or user.get("full_name") or bin_id
    pdf_name = f"{bin_id.replace('/', '_')}_{month_key}.pdf"
    pdf_path = REPORTS_DIR / pdf_name

    try:
        _render_pdf(pdf_path, business_name=business_name, bin_id=bin_id, month_label=month_label, metrics=metrics)
    except Exception as e:
        logger.error(f"[REPORT] PDF render failed for {email}: {e}")
        return None

    base_url = os.environ.get("APP_BASE_URL", "")
    pdf_url = f"{base_url}/api/static/reports/{pdf_name}" if base_url else f"/api/static/reports/{pdf_name}"

    # Upsert report record
    await _db.customer_reports.update_one(
        {"email": email, "month": month_key},
        {"$set": {
            "email": email,
            "bin": bin_id,
            "title": f"Report — {month_label}",
            "month": month_key,
            "url": pdf_url,
            "status": "ready",
            "metrics": metrics,
            "generated_at": now.isoformat(),
        }},
        upsert=True,
    )

    # Send via WhatsApp + Email (best-effort)
    phone = user.get("phone") or user.get("whatsapp") or ""
    if phone:
        try:
            from routers.whatsapp_alerts import send_whatsapp
            msg = f"Your AUREM monthly report is ready!\nView: {pdf_url}"
            await send_whatsapp(phone, msg)
        except Exception as e:
            logger.warning(f"[REPORT] WhatsApp send failed: {e}")

    try:
        # Email send via existing email_router if available
        from routers.email_service import send_email  # type: ignore
        await send_email(
            to=email,
            subject=f"Your AUREM monthly report — {month_label}",
            html=f"<p>Hi {business_name},</p><p>Your monthly report is ready. <a href='{pdf_url}'>View PDF</a>.</p>",
        )
    except Exception as e:
        logger.debug(f"[REPORT] Email send skipped: {e}")

    return {"url": pdf_url, "metrics": metrics, "month": month_key}


async def monthly_report_cron() -> Dict:
    """Run on 1st of month: generate reports for all active tenants."""
    if _db is None:
        return {"ok": False, "reason": "db_unset"}
    total = 0
    failed = 0
    cursor = _db.platform_users.find(
        {"business_id_active": True},
        {"_id": 0, "email": 1},
    )
    async for u in cursor:
        em = u.get("email", "")
        if not em:
            continue
        try:
            r = await generate_for_user(em)
            if r:
                total += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[REPORT] Cron {em} failed: {e}")
            failed += 1

    await _db.system_cron_log.insert_one({
        "job": "monthly_report",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "generated": total,
        "failed": failed,
    })
    return {"ok": True, "generated": total, "failed": failed}
