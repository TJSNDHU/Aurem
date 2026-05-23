"""
AUREM AI Appointment Scheduler Router
Google Calendar integration for booking skincare consultations
"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from urllib.parse import urlencode
import os
import secrets
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["appointments"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class AppointmentRequest(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = None
    appointment_type: str  # consultation, facial, treatment, followup
    preferred_date: str  # ISO date string
    preferred_time: str  # HH:MM format
    duration_minutes: int = 30
    notes: Optional[str] = None
    specialist_id: Optional[str] = None

class AppointmentUpdate(BaseModel):
    status: Optional[str] = None  # scheduled, confirmed, cancelled, completed
    new_date: Optional[str] = None
    new_time: Optional[str] = None
    notes: Optional[str] = None


# Appointment types and durations
APPOINTMENT_TYPES = {
    "consultation": {"name": "Skin Consultation", "duration": 30, "price": 0},
    "facial": {"name": "Facial Treatment", "duration": 60, "price": 150},
    "treatment": {"name": "Specialized Treatment", "duration": 90, "price": 250},
    "followup": {"name": "Follow-up Consultation", "duration": 20, "price": 0}
}

# Available time slots
BUSINESS_HOURS = {
    "start": "09:00",
    "end": "18:00",
    "slot_duration": 30  # minutes
}


# ──────────────────────────────────────────────────────────────────────
# iter 327h — Calendar invite + confirmation email helpers
# ──────────────────────────────────────────────────────────────────────

def _ics_dt(dt: datetime) -> str:
    """Format a UTC datetime as the iCalendar `DTSTART/DTEND` form
    (basic-format, no separators, `Z` suffix). Naive datetimes are
    treated as UTC for the calendar invite — same convention the rest
    of the codebase uses for appointment_datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ics_escape(s: str) -> str:
    """Escape a string for inclusion in an iCalendar TEXT field per RFC
    5545: escape `\\`, `,`, `;`, and fold newlines as `\\n`."""
    if not s:
        return ""
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def _build_ics(appointment: dict) -> str:
    """Generate a portable iCalendar invite for one appointment.
    Works in Google Calendar, Outlook, Apple Mail, Thunderbird."""
    start = appointment["appointment_datetime"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    duration_min = int(appointment.get("duration_minutes") or 30)
    end = start + timedelta(minutes=duration_min)
    uid = f"{appointment['appointment_id']}@aurem.live"
    summary = _ics_escape(
        appointment.get("appointment_type_name") or "AUREM Appointment"
    )
    desc_parts = [
        f"Customer: {appointment.get('customer_name','')}",
        f"Type: {appointment.get('appointment_type_name','')}",
    ]
    if appointment.get("notes"):
        desc_parts.append(f"Notes: {appointment['notes']}")
    desc_parts.append("Booked via AUREM.")
    description = _ics_escape("\n".join(desc_parts))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AUREM//Appointments//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_ics_dt(datetime.now(timezone.utc))}",
        f"DTSTART:{_ics_dt(start)}",
        f"DTEND:{_ics_dt(end)}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    # RFC 5545 requires CRLF line endings.
    return "\r\n".join(lines) + "\r\n"


def _build_google_calendar_quick_add_url(appointment: dict, base_url: str) -> str:
    """Build a Google Calendar `render?action=TEMPLATE` URL. One click
    from the confirmation email puts the event on the customer's own
    Google Calendar — no server-side OAuth required, no API key
    needed. For Outlook/Apple users, the `.ics` link in the email is
    the universal fallback."""
    start = appointment["appointment_datetime"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    duration_min = int(appointment.get("duration_minutes") or 30)
    end = start + timedelta(minutes=duration_min)
    params = {
        "action":  "TEMPLATE",
        "text":    appointment.get("appointment_type_name") or "AUREM Appointment",
        "dates":   f"{_ics_dt(start)}/{_ics_dt(end)}",
        "details": (
            f"Customer: {appointment.get('customer_name','')}\n"
            f"Booked via AUREM. Manage at {base_url}."
        ),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def _confirmation_email_html(appointment: dict, ics_url: str, gcal_url: str) -> str:
    """Compose the HTML body. Reuses the brand `base_template`
    helper from routers.email_service so the email looks consistent
    with welcome / order emails."""
    from routers.email_service import base_template
    start = appointment["appointment_datetime"]
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    pretty_when = start.strftime("%A, %B %d, %Y · %H:%M UTC")
    content = f"""
    <p style="margin-bottom:16px;">Hi {appointment.get('customer_name','there')},</p>
    <p style="margin-bottom:16px;">Your <strong>{appointment.get('appointment_type_name','AUREM appointment')}</strong> is confirmed.</p>
    <div style="background:#0d0d10;border:1px solid rgba(201,168,110,0.15);border-radius:8px;padding:20px;margin:24px 0;">
        <p style="font-family:sans-serif;font-size:10px;letter-spacing:0.15em;color:#8A6B38;margin:0 0 8px;text-transform:uppercase;">When</p>
        <p style="font-size:18px;color:#C9A86E;margin:0 0 4px;">{pretty_when}</p>
        <p style="font-size:13px;color:#A89880;margin:8px 0 0;">Duration: {appointment.get('duration_minutes', 30)} min</p>
    </div>
    <p style="margin:16px 0;">Add to your calendar in one click:</p>
    <p style="margin:8px 0;">
      &nbsp;•&nbsp; <a href="{gcal_url}" style="color:#C9A86E;">Add to Google Calendar</a><br/>
      &nbsp;•&nbsp; <a href="{ics_url}" style="color:#C9A86E;">Outlook / Apple / other calendar (.ics)</a>
    </p>
    <p style="color:#A89880;font-size:12px;margin-top:24px;">
      Reply to this email if you need to reschedule. Booking ref:
      <code style="color:#C9A86E;">{appointment.get('appointment_id','')}</code>.
    </p>
    """
    return base_template(
        "Your AUREM appointment is confirmed",
        content,
        cta_text="Add to Google Calendar",
        cta_link=gcal_url,
    )


async def _send_confirmation_email(appointment: dict, ics_url: str, gcal_url: str) -> dict:
    """Send the booking confirmation. Returns
        {"ok": True,  "message_id": "..."}
      OR {"ok": False, "error": "<reason>"}
    We DELIBERATELY avoid the fire-and-forget `email_service.send_email`
    wrapper because it returns True even when Gmail isn't connected —
    that's the lie that caused the original TODO. We call the gmail
    service directly so the API response tells the truth."""
    try:
        from routers.email_service import _get_gmail_service
        gmail = await _get_gmail_service()
        if not gmail:
            return {"ok": False, "error": "gmail_service_unavailable"}
        html = _confirmation_email_html(appointment, ics_url, gcal_url)
        result = await gmail.send_email(
            business_id=os.environ.get("DEFAULT_BUSINESS_ID", "default"),
            to=appointment["customer_email"],
            subject="Your AUREM appointment is confirmed",
            body_text=(
                f"Your AUREM appointment is confirmed.\n"
                f"When: {appointment['appointment_datetime']}\n"
                f"Add to Google Calendar: {gcal_url}\n"
                f"iCal (.ics) link: {ics_url}\n"
                f"Ref: {appointment['appointment_id']}\n"
            ),
            body_html=html,
        )
        if result.get("success") or result.get("message_id"):
            return {"ok": True, "message_id": result.get("message_id", "")}
        return {"ok": False, "error": result.get("error") or "send_failed"}
    except Exception as e:
        logger.warning(f"[appointments] confirmation send failed: {e}")
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


@router.get("/{appointment_id}/calendar.ics")
async def get_appointment_ics(appointment_id: str):
    """Public — serve the appointment as a downloadable .ics so anyone
    (Outlook, Apple Calendar, Thunderbird, any RFC-5545 client) can
    add it with one click. No auth — the appointment_id (16-hex secret)
    is the access control, same convention as `/api/report/{slug}`."""
    if db is None:
        raise HTTPException(503, "Database not ready")
    appt = await db.appointments.find_one(
        {"appointment_id": appointment_id}, {"_id": 0}
    )
    if not appt:
        raise HTTPException(404, "Appointment not found")
    ics = _build_ics(appt)
    return Response(
        content=ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="aurem-{appointment_id}.ics"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/types")
async def get_appointment_types():
    """Get available appointment types"""
    return {"types": APPOINTMENT_TYPES}


@router.get("/availability")
async def get_availability(date: str, specialist_id: Optional[str] = None):
    """Get available time slots for a specific date"""
    try:
        target_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
    except:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
    
    # Get existing appointments for the date
    start_of_day = target_date.replace(hour=0, minute=0, second=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59)
    
    query = {
        "appointment_datetime": {"$gte": start_of_day, "$lte": end_of_day},
        "status": {"$nin": ["cancelled"]}
    }
    if specialist_id:
        query["specialist_id"] = specialist_id
    
    booked = await db.appointments.find(query).to_list(100)
    booked_times = set()
    
    for appt in booked:
        appt_time = appt["appointment_datetime"]
        duration = appt.get("duration_minutes", 30)
        # Block all slots during appointment
        for i in range(0, duration, BUSINESS_HOURS["slot_duration"]):
            slot_time = appt_time + timedelta(minutes=i)
            booked_times.add(slot_time.strftime("%H:%M"))
    
    # Generate available slots
    available_slots = []
    current_time = datetime.strptime(BUSINESS_HOURS["start"], "%H:%M")
    end_time = datetime.strptime(BUSINESS_HOURS["end"], "%H:%M")
    
    while current_time < end_time:
        time_str = current_time.strftime("%H:%M")
        if time_str not in booked_times:
            available_slots.append({
                "time": time_str,
                "available": True
            })
        current_time += timedelta(minutes=BUSINESS_HOURS["slot_duration"])
    
    return {
        "date": date,
        "specialist_id": specialist_id,
        "available_slots": available_slots,
        "business_hours": BUSINESS_HOURS
    }


@router.post("/book")
async def book_appointment(data: AppointmentRequest, request: Request):
    """Book a new appointment.

    Bug-fix #176 (R21): authenticated callers only. Previously zero-auth
    let competitors flood the booking system with fake appointments to
    block legitimate ones.
    """
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))

    # Validate appointment type
    if data.appointment_type not in APPOINTMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid appointment type. Use: {list(APPOINTMENT_TYPES.keys())}")
    
    # Parse datetime
    try:
        appointment_datetime = datetime.fromisoformat(f"{data.preferred_date}T{data.preferred_time}:00")
    except:
        raise HTTPException(status_code=400, detail="Invalid date/time format")
    
    # Check availability
    query = {
        "appointment_datetime": appointment_datetime,
        "status": {"$nin": ["cancelled"]}
    }
    if data.specialist_id:
        query["specialist_id"] = data.specialist_id
    
    existing = await db.appointments.find_one(query)
    if existing:
        raise HTTPException(status_code=409, detail="Time slot already booked")
    
    # Create appointment
    appointment_id = f"appt_{secrets.token_hex(8)}"
    appointment_type_info = APPOINTMENT_TYPES[data.appointment_type]
    
    appointment = {
        "appointment_id": appointment_id,
        "customer_name": data.customer_name,
        "customer_email": data.customer_email,
        "customer_phone": data.customer_phone,
        "appointment_type": data.appointment_type,
        "appointment_type_name": appointment_type_info["name"],
        "appointment_datetime": appointment_datetime,
        "duration_minutes": data.duration_minutes or appointment_type_info["duration"],
        "price": appointment_type_info["price"],
        "specialist_id": data.specialist_id,
        "notes": data.notes,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.appointments.insert_one(appointment)

    # iter 327h — Honest replacement for the two old TODO lines:
    #   "Create Google Calendar event when credentials are available"
    #   "Send confirmation email"
    #
    # We DON'T build a third email path or pull in a new Google Calendar
    # SDK. Instead:
    #   1. Generate a portable .ics calendar invite (works on Google
    #      Calendar, Outlook, Apple Mail, etc.) — served from a
    #      public GET endpoint below.
    #   2. Generate a Google Calendar "quick add" URL so one click in
    #      the email puts the event on the customer's personal calendar.
    #   3. Send the confirmation email via the existing GmailService
    #      (the same path used by welcome / order-confirmation emails).
    #   4. Record `confirmation_email_sent_at` or
    #      `confirmation_email_error` on the appointment so the booking
    #      UI can show real send status — no more silently-true "step
    #      completed" markers.
    base_url = os.environ.get("APP_BASE_URL", "https://aurem.live").rstrip("/")
    ics_url   = f"{base_url}/api/appointments/{appointment_id}/calendar.ics"
    gcal_url  = _build_google_calendar_quick_add_url(appointment, base_url)
    appointment["ics_url"]  = ics_url
    appointment["gcal_url"] = gcal_url

    send_result = await _send_confirmation_email(
        appointment=appointment, ics_url=ics_url, gcal_url=gcal_url,
    )
    update_set = {"ics_url": ics_url, "gcal_url": gcal_url}
    if send_result.get("ok"):
        update_set["confirmation_email_sent_at"] = datetime.now(timezone.utc)
        if send_result.get("message_id"):
            update_set["confirmation_message_id"] = send_result["message_id"]
    else:
        update_set["confirmation_email_error"] = send_result.get("error", "unknown")
    await db.appointments.update_one(
        {"appointment_id": appointment_id}, {"$set": update_set}
    )
    appointment.update(update_set)

    del appointment["_id"]
    return {
        "success": True,
        "appointment": appointment,
        "confirmation_email_sent": bool(send_result.get("ok")),
        "confirmation_email_error": send_result.get("error") if not send_result.get("ok") else None,
        "ics_url": ics_url,
        "gcal_url": gcal_url,
        "message": f"Appointment booked for {appointment_datetime.strftime('%B %d, %Y at %H:%M')}",
    }


@router.get("/list")
async def list_appointments(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50
):
    """List appointments with filters"""
    query = {}
    
    if status:
        query["status"] = status
    
    if date_from:
        query["appointment_datetime"] = {"$gte": datetime.fromisoformat(date_from)}
    if date_to:
        if "appointment_datetime" in query:
            query["appointment_datetime"]["$lte"] = datetime.fromisoformat(date_to)
        else:
            query["appointment_datetime"] = {"$lte": datetime.fromisoformat(date_to)}
    
    appointments = await db.appointments.find(query, {"_id": 0}).sort("appointment_datetime", 1).limit(limit).to_list(limit)
    
    return {"appointments": appointments}


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str):
    """Get appointment details"""
    appointment = await db.appointments.find_one(
        {"appointment_id": appointment_id},
        {"_id": 0}
    )
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return {"appointment": appointment}


@router.patch("/{appointment_id}")
async def update_appointment(appointment_id: str, data: AppointmentUpdate):
    """Update or reschedule appointment"""
    update_data = {}
    
    if data.status:
        update_data["status"] = data.status
    
    if data.new_date and data.new_time:
        new_datetime = datetime.fromisoformat(f"{data.new_date}T{data.new_time}:00")
        update_data["appointment_datetime"] = new_datetime
    
    if data.notes:
        update_data["notes"] = data.notes
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    result = await db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return {"success": True, "message": "Appointment updated"}


@router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, request: Request):
    """Cancel an appointment.

    Bug-fix #176 (R21): admin auth required. Previously zero-auth +
    short guessable appointment_id let attackers cancel any booking.
    """
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))

    result = await db.appointments.update_one(
        {"appointment_id": appointment_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc)
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return {"success": True, "message": "Appointment cancelled"}


@router.get("/customer/{email}")
async def get_customer_appointments(email: str, request: Request):
    """Get all appointments for a customer.

    Bug-fix #176 (R21): admin auth required. Previously zero-auth let
    anyone enumerate every customer's appointment history by email.
    """
    from utils.admin_guard import verify_admin
    verify_admin(request.headers.get("Authorization", ""))

    appointments = await db.appointments.find(
        {"customer_email": email},
        {"_id": 0}
    ).sort("appointment_datetime", -1).to_list(50)
    
    return {"appointments": appointments}
