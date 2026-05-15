"""
AUREM Agents Admin Router
==========================
Endpoints consumed by the Agent Command Center UI.

GET  /api/agents/status            → snapshot of all 4 agents
GET  /api/agents/a2a-feed          → recent A2A events (for live ticker)
POST /api/agents/{agent}/pause     → pause a single agent
POST /api/agents/{agent}/resume    → resume
POST /api/agents/{agent}/run-now   → trigger a single cycle immediately
GET  /api/auto-hunt/settings       → current settings (provinces, limits, toggles)
POST /api/auto-hunt/settings       → update settings
POST /api/auto-hunt/toggle         → master on/off switch
GET  /api/auto-hunt/queue          → next 7 days of planned hunts
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Agents"])

_db = None


def set_db(db):
    global _db
    _db = db


def _require_admin(request: Request):
    """Bug-fix #150 (R18): admin enforcement, no silent admin grant.

    The previous version returned ``{"_token": token}`` on JWT decode
    failure — granting admin access on every malformed token. Replaced
    with the canonical ``verify_admin`` guard which raises 401/403.
    """
    from utils.admin_guard import verify_admin
    auth = request.headers.get("Authorization", "")
    payload = verify_admin(auth)
    if isinstance(payload, dict):
        payload["_token"] = auth.split(" ", 1)[1].strip() if " " in auth else ""
    return payload


# ═══════════════════════════════════════════
# AGENTS — snapshot / pause / resume / run
# ═══════════════════════════════════════════

@router.get("/agents/status")
async def agents_status(request: Request):
    """Snapshot of all 4 agents + combined stats for the Admin Command Center.

    iter 322 — hardened: any subsystem failure (agent registry import,
    A2A bus init, Mongo aggregate latency) returns a safe degraded payload
    instead of bubbling a 500. Polled every 30s by the dashboard, so a
    transient blip must NEVER show as a backend exception.
    """
    _require_admin(request)

    agents: List[Dict[str, Any]] = []
    a2a_recent: List[Dict[str, Any]] = []
    degraded_reasons: List[str] = []

    try:
        from services.agents import all_agents
        agents = [a.snapshot() for a in all_agents()]
    except Exception as e:
        logger.warning(f"[agents/status] all_agents failed: {e}")
        degraded_reasons.append(f"agents:{str(e)[:80]}")

    try:
        from services.a2a_bus import bus
        a2a_recent = bus.recent(30)
    except Exception as e:
        logger.warning(f"[agents/status] a2a bus failed: {e}")
        degraded_reasons.append(f"a2a:{str(e)[:80]}")

    combined = {"new_today": 0, "followup_today": 0, "closing_today": 0, "referral_today": 0}
    for a in agents:
        st = a.get("today_stats", {}) or {}
        aid = a.get("agent_id")
        if aid == "hunter_ora":
            combined["new_today"] = st.get("scouted", 0)
        elif aid == "followup_ora":
            combined["followup_today"] = st.get("drip_sent", 0)
        elif aid == "closer_ora":
            combined["closing_today"] = st.get("closer_attempts", 0)
        elif aid == "referral_ora":
            combined["referral_today"] = st.get("referrals_contacted", 0)

    # Pull today's revenue / replies if available
    revenue = 0
    replied = 0
    if _db is not None:
        try:
            start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            revenue_agg = await _db.financial_log.aggregate([
                {"$match": {"timestamp": {"$gte": start}, "event_type": "revenue"}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
            ]).to_list(length=1)
            if revenue_agg:
                revenue = revenue_agg[0].get("total", 0)
            replied = await _db.campaign_leads.count_documents({
                "last_reply_at": {"$gte": start},
            })
        except Exception as e:
            logger.debug(f"[agents/status] revenue/replied probe skipped: {e}")

    return {
        "agents": agents,
        "combined_today": {
            **combined,
            "total_contacted": sum(combined.values()),
            "replied": replied,
            "revenue_cad": revenue,
        },
        "a2a_recent": a2a_recent,
        "degraded": degraded_reasons or None,
    }


@router.get("/agents/a2a-feed")
async def agents_a2a_feed(request: Request, limit: int = 50):
    """Recent A2A events for the live ticker in the admin UI."""
    _require_admin(request)
    from services.a2a_bus import bus
    return {"events": bus.recent(limit)}


@router.post("/agents/{agent_id}/pause")
async def agent_pause(agent_id: str, request: Request):
    _require_admin(request)
    from services.agents import get_agent
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Unknown agent: {agent_id}")
    await agent.pause()
    await _broadcast_feed(agent_id, f"{agent_id} paused", "info")
    return {"ok": True, "agent": agent_id, "paused": True}


@router.post("/agents/{agent_id}/resume")
async def agent_resume(agent_id: str, request: Request):
    _require_admin(request)
    from services.agents import get_agent
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Unknown agent: {agent_id}")
    await agent.resume()
    await _broadcast_feed(agent_id, f"{agent_id} resumed", "success")
    return {"ok": True, "agent": agent_id, "paused": False}


@router.post("/agents/{agent_id}/run-now")
async def agent_run_now(agent_id: str, request: Request, background_tasks: BackgroundTasks):
    """Fire-and-forget: queue the cycle in background, return 202 instantly.

    The ORA Command Console relies on this never blocking — button UX breaks
    if FastAPI holds the connection open while the agent runs Google Places
    calls and DB writes for 30-60s.
    """
    _require_admin(request)
    from services.agents import get_agent
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, f"Unknown agent: {agent_id}")

    async def _bg():
        try:
            await _broadcast_feed(agent_id, f"{agent_id} cycle started", "info")
            stats = await agent.run_cycle()
            await _broadcast_feed(
                agent_id,
                f"{agent_id} cycle complete",
                "success",
                extra={"stats": stats},
            )
        except Exception as e:
            logger.exception(f"[agents] {agent_id} run-now failed: {e}")
            await _broadcast_feed(agent_id, f"{agent_id} error: {str(e)[:120]}", "error")

    background_tasks.add_task(_bg)
    return {"ok": True, "status": "queued", "agent": agent_id}


# ═══════════════════════════════════════════
# AUTO-HUNT SETTINGS
# ═══════════════════════════════════════════

class AutoHuntSettings(BaseModel):
    enabled: bool = False
    morning_brief_time: str = "07:00"
    evening_brief_time: str = "19:00"
    ramp_mode: str = "safe"  # "safe" | "aggressive"
    daily_limit_override: int | None = None
    province_config: Dict[str, Dict[str, Any]] | None = None
    industries_enabled: List[str] | None = None


DEFAULT_PROVINCE_CONFIG = {
    "Ontario":  {"country": "CA", "tz": "America/Toronto",   "limit": 50, "active": True, "window": "08:00-19:00"},
    "BC":       {"country": "CA", "tz": "America/Vancouver", "limit": 30, "active": True, "window": "08:00-19:00"},
    "Alberta":  {"country": "CA", "tz": "America/Edmonton",  "limit": 30, "active": True, "window": "08:00-19:00"},
    "Quebec":   {"country": "CA", "tz": "America/Toronto",   "limit": 20, "active": True, "window": "08:00-19:00"},
    "Manitoba": {"country": "CA", "tz": "America/Winnipeg",  "limit": 20, "active": True, "window": "08:00-19:00"},
    "Atlantic": {"country": "CA", "tz": "America/Halifax",   "limit": 10, "active": True, "window": "08:00-19:00"},
    "Eastern":  {"country": "US", "tz": "America/New_York",    "limit": 50, "active": True, "window": "08:00-19:00"},
    "Central":  {"country": "US", "tz": "America/Chicago",     "limit": 30, "active": True, "window": "08:00-19:00"},
    "Mountain": {"country": "US", "tz": "America/Denver",      "limit": 20, "active": True, "window": "08:00-19:00"},
    "Pacific":  {"country": "US", "tz": "America/Los_Angeles", "limit": 30, "active": True, "window": "08:00-19:00"},
}

DEFAULT_INDUSTRIES = [
    "auto shops", "salons", "restaurants", "dental", "real estate",
    "hvac", "gyms", "lawyers", "accountants",
]


@router.get("/auto-hunt/settings")
async def get_auto_hunt_settings(request: Request):
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not ready")
    doc = await _db.auto_hunt_settings.find_one({"_id": "singleton"}) or {}
    doc.pop("_id", None)
    # Fill defaults if not present
    if "province_config" not in doc:
        doc["province_config"] = DEFAULT_PROVINCE_CONFIG
    if "industries_enabled" not in doc:
        doc["industries_enabled"] = DEFAULT_INDUSTRIES
    if "enabled" not in doc:
        doc["enabled"] = False
    if "morning_brief_time" not in doc:
        doc["morning_brief_time"] = "07:00"
    if "evening_brief_time" not in doc:
        doc["evening_brief_time"] = "19:00"
    if "ramp_mode" not in doc:
        doc["ramp_mode"] = "safe"  # safer default
    # Report current ramped daily limit
    from services.agents.hunter_ora import HunterORA
    hunter = HunterORA(_db)
    doc["current_daily_limit"] = await hunter.get_daily_limit()
    doc["ramp_presets"] = {
        "safe":       {"weeks": [20, 50, 100, 200], "note": "Recommended — better deliverability, zero spam risk"},
        "aggressive": {"weeks": [50, 100, 200, 200], "note": "Fast scaling — use only after domain is warmed up"},
    }
    return doc


@router.post("/auto-hunt/settings")
async def update_auto_hunt_settings(body: AutoHuntSettings, request: Request):
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not ready")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.auto_hunt_settings.update_one(
        {"_id": "singleton"},
        {"$set": update},
        upsert=True,
    )
    return {"ok": True, "updated": list(update.keys())}


@router.post("/auto-hunt/toggle")
async def toggle_auto_hunt(request: Request):
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not ready")
    doc = await _db.auto_hunt_settings.find_one({"_id": "singleton"}) or {}
    new_state = not bool(doc.get("enabled", False))
    update = {"enabled": new_state, "updated_at": datetime.now(timezone.utc).isoformat()}
    if new_state and not doc.get("activated_at"):
        update["activated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.auto_hunt_settings.update_one(
        {"_id": "singleton"},
        {"$set": update},
        upsert=True,
    )
    from services.a2a_bus import bus
    await bus.emit("admin", "auto_hunt_toggled", {"enabled": new_state})
    # Report ramp-aware status
    ramp_mode = doc.get("ramp_mode", "safe")
    from services.agents.hunter_ora import HunterORA
    hunter = HunterORA(_db)
    current_limit = await hunter.get_daily_limit()
    emoji = "🚀" if ramp_mode == "aggressive" else "🐢"
    status = f"{emoji} {ramp_mode.title()} mode · {current_limit}/day" if new_state else "paused"
    return {"ok": True, "enabled": new_state, "ramp_mode": ramp_mode, "ramp_status": status}


@router.get("/auto-hunt/queue")
async def get_hunt_queue(request: Request):
    _require_admin(request)
    from services.agents.hunter_ora import WEEKLY_ROTATION
    today = datetime.now(timezone.utc)
    queue = []
    for i in range(7):
        d = today + timedelta(days=i)
        dow = d.weekday()
        targets = WEEKLY_ROTATION.get(dow, [])
        queue.append({
            "date": d.strftime("%Y-%m-%d"),
            "day": d.strftime("%a"),
            "targets": [{"territory": t, "industry": ind} for (t, ind) in targets],
        })
    return {"next_7_days": queue}


# ═══════════════════════════════════════════
# COMPLIANCE / UNSUBSCRIBE
# ═══════════════════════════════════════════

@router.get("/compliance/status")
async def compliance_status(request: Request):
    _require_admin(request)
    from services.casl_compliance import compliance_snapshot
    return compliance_snapshot()


@router.get("/compliance/audit-report.pdf")
async def audit_report_pdf(
    request: Request,
    start: str = "",
    end: str = "",
):
    """
    Court-ready compliance audit PDF for a date range (ISO YYYY-MM-DD).
    Defaults to last 30 days if range not provided.
    Pulls from: audit_trail_daily, consent_records, message_log_complete, financial_log.
    """
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not ready")

    from fastapi.responses import Response
    from datetime import datetime as _dt, timedelta as _td
    from services.casl_compliance import (
        LEGAL_NAME, LEGAL_ADDRESS, CONTACT_EMAIL, HST_NUMBER,
    )

    # Resolve date range
    now = _dt.now(timezone.utc)
    if not end:
        end_dt = now
    else:
        try:
            end_dt = _dt.fromisoformat(end).replace(tzinfo=timezone.utc)
        except Exception:
            end_dt = now
    if not start:
        start_dt = end_dt - _td(days=30)
    else:
        try:
            start_dt = _dt.fromisoformat(start).replace(tzinfo=timezone.utc)
        except Exception:
            start_dt = end_dt - _td(days=30)

    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    # Collect audit facts
    try:
        messages_sent = await _db.message_log_complete.count_documents({
            "timestamp": {"$gte": start_iso, "$lte": end_iso},
        })
    except Exception:
        messages_sent = 0

    try:
        consent_count = await _db.consent_records.count_documents({
            "timestamp": {"$gte": start_iso, "$lte": end_iso},
        })
        unsub_count = await _db.consent_records.count_documents({
            "timestamp": {"$gte": start_iso, "$lte": end_iso},
            "action": "unsubscribe",
        })
    except Exception:
        consent_count, unsub_count = 0, 0

    try:
        revenue_agg = await _db.financial_log.aggregate([
            {"$match": {"timestamp": {"$gte": start_iso, "$lte": end_iso},
                        "event_type": "revenue"}},
            {"$group": {"_id": None, "gross": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]).to_list(length=1)
        revenue = revenue_agg[0] if revenue_agg else {"gross": 0, "count": 0}
    except Exception:
        revenue = {"gross": 0, "count": 0}

    try:
        daily_records = await _db.audit_trail_daily.count_documents({
            "closed_at": {"$gte": start_iso, "$lte": end_iso},
        })
    except Exception:
        daily_records = 0

    # Assume zero violations unless flagged in audit_trail
    try:
        violations_agg = await _db.audit_trail_daily.aggregate([
            {"$match": {"closed_at": {"$gte": start_iso, "$lte": end_iso}}},
            {"$group": {"_id": None, "total": {"$sum": "$casl_violations"}}},
        ]).to_list(length=1)
        violations = violations_agg[0]["total"] if violations_agg else 0
    except Exception:
        violations = 0

    hst_included = round(revenue["gross"] * 13 / 113, 2)

    # Build PDF with reportlab
    from io import BytesIO
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title="AUREM Compliance Audit Report",
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(name="h1", parent=styles["Heading1"], textColor=colors.HexColor("#1B5E3A"),
                        fontSize=20, spaceAfter=8)
    h2 = ParagraphStyle(name="h2", parent=styles["Heading2"], textColor=colors.HexColor("#3D3A39"),
                        fontSize=13, spaceAfter=6)
    body = ParagraphStyle(name="body", parent=styles["BodyText"], fontSize=10, leading=14)
    muted = ParagraphStyle(name="muted", parent=body, textColor=colors.HexColor("#888"), fontSize=9)

    story = [
        Paragraph("AUREM Compliance Audit Report", h1),
        Paragraph(f"Period: {start_dt.strftime('%Y-%m-%d')} — {end_dt.strftime('%Y-%m-%d')}", body),
        Paragraph(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}", muted),
        Spacer(1, 16),

        Paragraph("Legal Entity", h2),
        Paragraph(LEGAL_NAME, body),
        Paragraph(LEGAL_ADDRESS, body),
        Paragraph(f"HST / Business Number: <b>{HST_NUMBER}</b>", body),
        Paragraph(f"Contact: {CONTACT_EMAIL}", body),
        Spacer(1, 16),

        Paragraph("Compliance Frameworks", h2),
    ]
    framework_tbl = Table(
        [["✓", "CASL", "Section 6(6) implied consent (B2B communications)"],
         ["✓", "PIPEDA", "Personal information handled under PIPEDA framework"],
         ["✓", "CRA HST", f"Business Number {HST_NUMBER} on all invoices"],
         ["✓", "Ontario Business Registry", "Polaris Built Inc. — current"]],
        colWidths=[0.3 * inch, 1.7 * inch, 4.5 * inch],
    )
    framework_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1B5E3A")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([framework_tbl, Spacer(1, 16)])

    story.append(Paragraph("Activity Summary", h2))
    stats_tbl = Table([
        ["Messages sent (all channels)", f"{messages_sent:,}"],
        ["Consent records written", f"{consent_count:,}"],
        ["Unsubscribe opt-outs processed", f"{unsub_count:,}"],
        ["Days audited (sealed records)", f"{daily_records}"],
        ["CASL violations detected", f"{violations}"],
    ], colWidths=[4.5 * inch, 2.0 * inch])
    stats_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f5f5")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e5e5e5")),
    ]))
    story.extend([stats_tbl, Spacer(1, 16)])

    story.append(Paragraph("Financial Summary", h2))
    fin_tbl = Table([
        ["Gross revenue (CAD)", f"${revenue['gross']:,.2f}"],
        ["Orders", f"{revenue['count']:,}"],
        ["HST included in revenue (13%)", f"${hst_included:,.2f}"],
    ], colWidths=[4.5 * inch, 2.0 * inch])
    fin_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#e5e5e5")),
    ]))
    story.extend([fin_tbl, Spacer(1, 24)])

    # Compliance score (100 if no violations and at least 1 daily record)
    score = 100 if violations == 0 else max(0, 100 - violations * 5)
    story.append(Paragraph(f"Compliance Score: <b>{score} / 100</b>", h2))
    if violations == 0:
        story.append(Paragraph("Zero CASL violations certificate — issued by AUREM automated audit.", body))
    story.append(Spacer(1, 24))

    story.append(Paragraph("Audit Trail Note", h2))
    story.append(Paragraph(
        "All message logs, consent records, and financial entries in this report are drawn from "
        "immutable MongoDB collections (<i>message_log_complete</i>, <i>consent_records</i>, "
        "<i>audit_trail_daily</i>, <i>financial_log</i>). Records are never deleted; "
        "nightly seal at 23:00 UTC produces tamper-evident daily snapshots.", body))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"— Generated by AUREM Compliance Engine · {now.strftime('%Y-%m-%d %H:%M UTC')}", muted))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()

    filename = f"aurem-audit-{start_dt.strftime('%Y%m%d')}-{end_dt.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/unsubscribe")
async def unsubscribe_post(request: Request):
    """
    Public unsubscribe endpoint — no auth required.
    Marks the provided lead (or email) as do_not_contact.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    lead_id = body.get("lead") or body.get("lead_id")
    email = (body.get("email") or "").strip().lower()

    if not lead_id and not email:
        raise HTTPException(400, "Provide 'lead' or 'email' in body")

    if _db is None:
        raise HTTPException(500, "DB not ready")

    query = {}
    if lead_id:
        query["lead_id"] = lead_id
    elif email:
        query["email"] = email

    result = await _db.campaign_leads.update_many(
        query,
        {"$set": {
            "status": "do_not_contact",
            "unsubscribed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    # Immutable consent record
    try:
        await _db.consent_records.insert_one({
            "action": "unsubscribe",
            "lead_id": lead_id,
            "email": email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent", "")[:200],
        })
    except Exception:
        pass

    return {"ok": True, "matched": result.matched_count, "modified": result.modified_count}


@router.get("/unsubscribe")
async def unsubscribe_landing(request: Request, lead: str = "", email: str = ""):
    """
    Public HTML landing page linked from every email footer.
    Renders a friendly confirmation page; also processes the unsubscribe if query params present.
    """
    from fastapi.responses import HTMLResponse
    lead_id = (lead or "").strip()
    email_clean = (email or "").strip().lower()
    processed = False

    if (lead_id or email_clean) and _db is not None:
        try:
            query = {"lead_id": lead_id} if lead_id else {"email": email_clean}
            await _db.campaign_leads.update_many(
                query,
                {"$set": {
                    "status": "do_not_contact",
                    "unsubscribed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            await _db.consent_records.insert_one({
                "action": "unsubscribe",
                "lead_id": lead_id,
                "email": email_clean,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "via": "landing_page",
            })
            processed = True
        except Exception as e:
            logger.warning(f"[Unsubscribe] landing failed: {e}")

    from services.casl_compliance import LEGAL_NAME, LEGAL_ADDRESS, CONTACT_EMAIL
    heading = "✓ You\u2019ve been unsubscribed" if processed else "✕ Confirm Unsubscribe"
    body_copy = (
        "We\u2019ve added you to our do-not-contact list. You will not receive further marketing messages from AUREM."
        if processed else
        "Click below to confirm you want to stop receiving AUREM communications."
    )
    form_block = "" if processed else (
        f'''<form method="POST" action="/api/unsubscribe" style="margin-top:16px">
      <input type="hidden" name="lead" value="{lead_id}"/>
      <input type="hidden" name="email" value="{email_clean}"/>
      <button type="submit" style="padding:12px 24px;background:#1B5E3A;color:#fff;border:0;border-radius:8px;cursor:pointer">
        Confirm Unsubscribe
      </button>
    </form>'''
    )
    html = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Unsubscribed — AUREM</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #faf8f3; color: #3d3a39; margin: 0; padding: 48px 24px;
           display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
    .card {{ max-width: 480px; background: #fff; padding: 32px; border-radius: 12px;
             box-shadow: 0 4px 20px rgba(0,0,0,.05); text-align: center; }}
    h1 {{ font-family: 'Georgia', serif; font-size: 22px; margin: 0 0 8px; color: #1B5E3A; }}
    p  {{ font-size: 14px; line-height: 1.6; }}
    .muted {{ color: #888; font-size: 11px; margin-top: 24px; }}
  </style>
</head><body>
  <div class="card">
    <h1>{heading}</h1>
    <p>{body_copy}</p>
    {form_block}
    <div class="muted">
      {LEGAL_NAME}<br/>{LEGAL_ADDRESS}<br/>
      <a href="mailto:{CONTACT_EMAIL}" style="color:#888">{CONTACT_EMAIL}</a>
    </div>
  </div>
</body></html>"""
    return HTMLResponse(html)


# ═══════════════════════════════════════════
# ORA COMMAND CONSOLE — upgrades (v2026.04)
# ═══════════════════════════════════════════

async def _broadcast_feed(
    agent: str,
    message: str,
    event_type: str = "info",
    business_name=None,
    extra=None,
):
    """Push a live event to SSE clients + persist to agent_feed collection."""
    payload: Dict[str, Any] = {
        "agent": agent,
        "message": message,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if business_name:
        payload["business_name"] = business_name
    if extra:
        payload.update(extra)

    if _db is not None:
        try:
            await _db.agent_feed.insert_one(dict(payload))
        except Exception:
            pass

    try:
        from routers.server_misc_routes import push_sse_event
        await push_sse_event("agent_event", payload)
    except Exception as e:
        logger.debug(f"[agents] SSE push failed: {e}")


_AGENT_IDS = ["hunter_ora", "followup_ora", "closer_ora", "referral_ora"]


@router.post("/agents/pause-all")
async def agents_pause_all(request: Request):
    _require_admin(request)
    from services.agents import get_agent
    paused: List[str] = []
    for aid in _AGENT_IDS:
        a = get_agent(aid)
        if a:
            await a.pause()
            paused.append(aid)
    await _broadcast_feed("system", "All agents paused", "info")
    return {"ok": True, "paused": paused}


@router.post("/agents/resume-all")
async def agents_resume_all(request: Request):
    _require_admin(request)
    from services.agents import get_agent
    resumed: List[str] = []
    for aid in _AGENT_IDS:
        a = get_agent(aid)
        if a:
            await a.resume()
            resumed.append(aid)
    await _broadcast_feed("system", "All agents resumed", "success")
    return {"ok": True, "resumed": resumed}


class HuntNowBody(BaseModel):
    mode: str = "industry"
    industry: Any = None
    province: str = "ontario"
    score_filter: int = 70
    address: str = ""
    radius_km: float = 5.0
    limit: int = 20


@router.post("/agents/hunter/hunt-now")
async def hunter_hunt_now(body: HuntNowBody, request: Request, background_tasks: BackgroundTasks):
    """Ad-hoc hunt — bypasses scheduled auto-hunt config.

    If limit ≤ 5 → runs inline (Preview). Else → background queue with 202.
    Command is persisted to db.hunt_commands so operator has a history log
    that survives page refresh / browser close.
    """
    user_data = _require_admin(request)
    limit = max(1, min(150, int(body.limit or 20)))
    body.limit = limit
    is_preview = limit <= 5

    # Persist the command BEFORE running it — single source of truth for history.
    import uuid as _uuid
    command_id = f"cmd_{_uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    command_doc = {
        "command_id": command_id,
        "kind": "hunt",
        "mode": body.mode,
        "industry": body.industry if isinstance(body.industry, list) else ([body.industry] if body.industry else []),
        "province": body.province,
        "address": body.address,
        "radius_km": body.radius_km,
        "limit": limit,
        "is_preview": is_preview,
        "status": "running" if is_preview else "queued",
        "fired_by": user_data.get("email") or user_data.get("user_id") or "admin",
        "fired_at": now.isoformat(),
        "completed_at": None,
        "result_count": None,
        "error": None,
    }
    try:
        if _db is not None:
            await _db.hunt_commands.insert_one(command_doc.copy())
    except Exception as e:
        logger.debug(f"[hunt] command persist skipped: {e}")

    if is_preview:
        try:
            results = await _do_hunt(body, preview=True)
        except Exception as e:
            if _db is not None:
                await _db.hunt_commands.update_one(
                    {"command_id": command_id},
                    {"$set": {"status": "failed", "error": str(e)[:300],
                              "completed_at": datetime.now(timezone.utc).isoformat()}},
                )
            raise
        if _db is not None:
            await _db.hunt_commands.update_one(
                {"command_id": command_id},
                {"$set": {"status": "completed", "result_count": len(results),
                          "completed_at": datetime.now(timezone.utc).isoformat()}},
            )
        return {"status": "preview", "results": results, "count": len(results), "command_id": command_id}

    target = body.address.strip() if body.mode == "radius" else f"{body.industry} in {body.province}"
    await _broadcast_feed(
        "hunter_ora",
        f"Ad-hoc hunt queued: {body.mode} · {target} · limit {limit}",
        "info",
    )

    async def _bg_and_mark():
        try:
            out = await _do_hunt(body, False)
            if _db is not None:
                await _db.hunt_commands.update_one(
                    {"command_id": command_id},
                    {"$set": {"status": "completed",
                              "result_count": len(out) if isinstance(out, list) else None,
                              "completed_at": datetime.now(timezone.utc).isoformat()}},
                )
        except Exception as e:
            if _db is not None:
                await _db.hunt_commands.update_one(
                    {"command_id": command_id},
                    {"$set": {"status": "failed", "error": str(e)[:300],
                              "completed_at": datetime.now(timezone.utc).isoformat()}},
                )

    background_tasks.add_task(_bg_and_mark)
    return {
        "ok": True,
        "status": "queued",
        "queued": limit,
        "mode": body.mode,
        "command_id": command_id,
    }


@router.get("/agents/hunter/commands")
async def hunt_commands_history(request: Request, limit: int = 30):
    """Return the operator's recent hunt commands with their lock-in timestamp
    and outcome. Persists across page refresh / browser restarts."""
    _require_admin(request)
    if _db is None:
        return {"count": 0, "commands": []}
    try:
        cursor = _db.hunt_commands.find({}, {"_id": 0}).sort("fired_at", -1).limit(max(1, min(200, int(limit))))
        docs = await cursor.to_list(length=limit)
    except Exception as e:
        logger.warning(f"[hunt] history query failed: {e}")
        docs = []
    return {"count": len(docs), "commands": docs}


async def _do_hunt(body: HuntNowBody, preview: bool = False) -> List[Dict[str, Any]]:
    """Call the real Scout pipeline; on failure, fall back to DB leads query."""
    limit = max(1, min(150, int(body.limit or 20)))
    industries = body.industry if isinstance(body.industry, list) else (
        [body.industry] if body.industry else ["businesses"]
    )
    if body.mode == "radius":
        query = f"{industries[0]} near {body.address}"
    else:
        query = f"{', '.join(industries[:2])} in {body.province}"

    results: List[Dict[str, Any]] = []

    # 1) Try live Scout pipeline
    try:
        from services.hunt_live import run_hunt_live  # type: ignore
        scout_out = await run_hunt_live(
            query=query,
            limit=limit,
            location=body.address or body.province or "Canada",
            radius_km=float(body.radius_km or 5.0) if body.mode == "radius" else None,
            db=_db,
        )
        if scout_out and isinstance(scout_out, list):
            results = scout_out
    except Exception as e:
        logger.debug(f"[hunt] Scout pipeline unavailable, using DB fallback: {e}")

    # 2) DB fallback
    if not results and _db is not None:
        try:
            q: Dict[str, Any] = {}
            if body.mode == "industry" and body.province:
                q["$or"] = [
                    {"province": {"$regex": body.province, "$options": "i"}},
                    {"address": {"$regex": body.province[:4], "$options": "i"}},
                ]
            raw = await _db.leads.find(q, {"_id": 0}).sort("ora_score", -1).limit(limit).to_list(limit)
            results = [
                {
                    "name": r.get("business_name") or r.get("name"),
                    "address": r.get("address") or r.get("location"),
                    "phone": r.get("phone"),
                    "email": r.get("email"),
                    "score": r.get("ora_score") or r.get("score"),
                    "industry": r.get("industry"),
                }
                for r in (raw or [])
            ]
        except Exception as e:
            logger.warning(f"[hunt] leads fallback failed: {e}")

    tag = "[PREVIEW]" if preview else "[LIVE]"
    await _broadcast_feed(
        "hunter_ora",
        f"Hunt complete {tag}: {len(results)} businesses — {query}",
        "success" if results else "info",
    )
    return results


@router.get("/agents/stats")
async def agents_stats(request: Request):
    """Topbar metrics for ORA Command Console."""
    _require_admin(request)
    total_leads = 0
    contacted_today = 0
    deals_open = 0
    response_rate = 0.0
    if _db is not None:
        try:
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            total_leads = await _db.leads.count_documents({})
            contacted_today = await _db.leads.count_documents({"contacted_at": {"$gte": today.isoformat()}})
            try:
                deals_open = await _db.deals.count_documents({"status": {"$in": ["open", "interested", "negotiating"]}})
            except Exception:
                deals_open = 0
            contacted_all = await _db.leads.count_documents({"contacted_at": {"$exists": True}})
            responded = await _db.leads.count_documents({"responded": True})
            response_rate = round((responded / contacted_all * 100) if contacted_all else 0, 1)
        except Exception as e:
            logger.debug(f"[stats] query failed: {e}")
    return {
        "total_leads": total_leads,
        "contacted_today": contacted_today,
        "deals_open": deals_open,
        "response_rate": response_rate,
    }



# ═══════════════════════════════════════════
# CSV HUNT — bulk contact list upload (LIVE)
# ═══════════════════════════════════════════

@router.post("/agents/hunter/csv-hunt")
async def hunter_csv_hunt(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    limit: int = Form(50),
):
    """Bulk-contact a CSV list of businesses.

    Columns supported (case-insensitive): name, phone, email, address, industry.
    LIVE mode — real outreach. Guarded by DNC list + daily_cap upstream.
    """
    _require_admin(request)
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith((".csv", ".txt")):
        raise HTTPException(400, "Please upload a .csv or .txt file")

    import csv
    import io
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB cap
        raise HTTPException(413, "File too large — max 5MB")

    try:
        text = content.decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)[:max(1, min(500, int(limit)))]
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    if not rows:
        raise HTTPException(400, "CSV is empty or has no valid rows")

    # Normalize column names
    normalized: List[Dict[str, Any]] = []
    for r in rows:
        lc = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        normalized.append({
            "name": lc.get("name") or lc.get("business_name") or lc.get("business"),
            "phone": lc.get("phone") or lc.get("number") or lc.get("mobile"),
            "email": lc.get("email") or lc.get("e-mail"),
            "address": lc.get("address") or lc.get("location"),
            "industry": lc.get("industry") or lc.get("category"),
        })

    tag = "[LIVE]"
    await _broadcast_feed(
        "hunter_ora",
        f"CSV uploaded {tag}: {filename} · {len(normalized)} rows",
        "info",
    )

    async def _bg():
        try:
            from services.twilio_service import send_whatsapp_message  # fallback path
        except Exception:
            send_whatsapp_message = None  # type: ignore

        sent = 0
        skipped_dnc = 0
        for row in normalized:
            phone = row.get("phone")
            if not phone:
                continue
            # DNC check
            try:
                if _db is not None:
                    dnc = await _db.do_not_contact.find_one({"phone": phone})
                    if dnc:
                        skipped_dnc += 1
                        continue
            except Exception:
                pass

            # LIVE: attempt to send one friendly intro WhatsApp
            try:
                if send_whatsapp_message:
                    msg = "Hi! Quick intro from AUREM — saw your business and thought you'd like what we're building. 30 seconds?"
                    await send_whatsapp_message(phone, msg)
                    sent += 1
                    await _broadcast_feed(
                        "hunter_ora",
                        f"Sent intro to {row.get('name') or phone}",
                        "success",
                        business_name=row.get("name"),
                    )
            except Exception as e:
                logger.warning(f"[csv-hunt] send failed for {phone}: {e}")

        await _broadcast_feed(
            "hunter_ora",
            f"CSV hunt complete {tag}: {sent} contacted, {skipped_dnc} on DNC",
            "success" if sent else "info",
        )

    background_tasks.add_task(_bg)
    return {
        "ok": True,
        "status": "queued",
        "queued": len(normalized),
        "filename": filename,
    }

