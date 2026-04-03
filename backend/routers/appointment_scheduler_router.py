"""
ReRoots AI Appointment Scheduler Router
Google Calendar integration for booking skincare consultations
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import secrets

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
async def book_appointment(data: AppointmentRequest):
    """Book a new appointment"""
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
    
    # TODO: Create Google Calendar event when credentials are available
    # TODO: Send confirmation email
    
    del appointment["_id"]
    return {
        "success": True,
        "appointment": appointment,
        "message": f"Appointment booked for {appointment_datetime.strftime('%B %d, %Y at %H:%M')}"
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
async def cancel_appointment(appointment_id: str):
    """Cancel an appointment"""
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
async def get_customer_appointments(email: str):
    """Get all appointments for a customer"""
    appointments = await db.appointments.find(
        {"customer_email": email},
        {"_id": 0}
    ).sort("appointment_datetime", -1).to_list(50)
    
    return {"appointments": appointments}
