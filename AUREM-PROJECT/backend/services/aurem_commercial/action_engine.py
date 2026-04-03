"""
AUREM Commercial Platform - Action Engine
The "Hands" of the Agent Swarm - Execute real-world actions

REUSES EXISTING INFRASTRUCTURE:
- MCP Server (/routes/mcp_routes.py) - Tool registry
- Appointment Scheduler (/routers/appointment_scheduler_router.py) - Calendar
- Stripe Billing (/routers/aurem_billing_router.py) - Payments
- Gmail Service (/services/aurem_commercial/gmail_service.py) - Email
- Vanguard (/routers/aurem_vanguard_router.py) - Lead generation swarm

Features:
- Unified tool registry for AI function calling
- Google Calendar: Check availability, book appointments
- Stripe: Generate invoices, payment links  
- Email: Send via connected Gmail
- WhatsApp: Send via Twilio/WHAPI
- Push results to WebSocket Live Activity feed
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ActionType(str, Enum):
    CALENDAR_CHECK = "calendar.check_availability"
    CALENDAR_BOOK = "calendar.book_appointment"
    STRIPE_INVOICE = "stripe.create_invoice"
    STRIPE_LINK = "stripe.create_payment_link"
    EMAIL_SEND = "email.send"
    WHATSAPP_SEND = "whatsapp.send"


class ActionResult(BaseModel):
    action_id: str
    action_type: ActionType
    status: ActionStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "check_calendar_availability", "description": "Check available time slots", "parameters": {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]}}},
    {"type": "function", "function": {"name": "book_appointment", "description": "Book appointment with calendar invite", "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "start_time": {"type": "string"}, "attendee_email": {"type": "string"}}, "required": ["title", "start_time", "attendee_email"]}}},
    {"type": "function", "function": {"name": "create_invoice", "description": "Create Stripe invoice", "parameters": {"type": "object", "properties": {"customer_email": {"type": "string"}, "items": {"type": "array"}}, "required": ["customer_email", "items"]}}},
    {"type": "function", "function": {"name": "create_payment_link", "description": "Create Stripe payment link", "parameters": {"type": "object", "properties": {"product_name": {"type": "string"}, "amount": {"type": "number"}}, "required": ["product_name", "amount"]}}},
    {"type": "function", "function": {"name": "send_email", "description": "Send email via Gmail", "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}}},
    {"type": "function", "function": {"name": "send_whatsapp", "description": "Send WhatsApp message", "parameters": {"type": "object", "properties": {"phone": {"type": "string"}, "message": {"type": "string"}}, "required": ["phone", "message"]}}}
]


class ActionEngine:
    def __init__(self, db):
        self.db = db
        self.collection = db["aurem_actions"]
    
    def get_tool_definitions(self) -> List[Dict]:
        return TOOL_DEFINITIONS
    
    async def execute(self, business_id: str, action_type: ActionType, params: Dict, triggered_by: str = "orchestrator", ip: str = None) -> ActionResult:
        import uuid
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        started_at = datetime.now(timezone.utc)
        
        await self.collection.insert_one({"action_id": action_id, "business_id": business_id, "action_type": action_type.value, "params": params, "status": "running", "started_at": started_at})
        
        try:
            if action_type == ActionType.CALENDAR_CHECK:
                data = await self._check_availability(business_id, params)
            elif action_type == ActionType.CALENDAR_BOOK:
                data = await self._book_appointment(business_id, params, ip)
            elif action_type == ActionType.STRIPE_INVOICE:
                data = await self._create_invoice(business_id, params)
            elif action_type == ActionType.STRIPE_LINK:
                data = await self._create_payment_link(business_id, params)
            elif action_type == ActionType.EMAIL_SEND:
                data = await self._send_email(business_id, params, ip)
            elif action_type == ActionType.WHATSAPP_SEND:
                data = await self._send_whatsapp(params)
            else:
                raise ValueError(f"Unknown: {action_type}")
            
            result = ActionResult(action_id=action_id, action_type=action_type, status=ActionStatus.SUCCESS, result=data, started_at=started_at, completed_at=datetime.now(timezone.utc))
        except Exception as e:
            result = ActionResult(action_id=action_id, action_type=action_type, status=ActionStatus.FAILED, error=str(e), started_at=started_at, completed_at=datetime.now(timezone.utc))
        
        await self.collection.update_one({"action_id": action_id}, {"$set": {"status": result.status.value, "result": result.result, "error": result.error}})
        await self._push_activity(business_id, action_type, result, triggered_by)
        return result
    
    async def _push_activity(self, business_id: str, action_type: ActionType, result: ActionResult, agent: str):
        try:
            from services.aurem_commercial import get_aurem_memory, get_websocket_hub
            memory = await get_aurem_memory()
            hub = await get_websocket_hub()
            icons = {ActionType.CALENDAR_BOOK: "📅", ActionType.STRIPE_INVOICE: "💰", ActionType.STRIPE_LINK: "💳", ActionType.EMAIL_SEND: "📧", ActionType.WHATSAPP_SEND: "💬"}
            icon = icons.get(action_type, "⚡")
            desc = f"{icon} {agent.title()} completed {action_type.value.split('.')[1]}" if result.status == ActionStatus.SUCCESS else f"⚠️ Action failed"
            await memory.log_activity(business_id, "action", desc)
            await hub.push_activity(business_id, "action", desc, icon)
        except Exception as e:
            logger.error(f"Activity push failed: {e}")
    
    async def _check_availability(self, business_id: str, params: Dict) -> Dict:
        date_str = params.get("date")
        target = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        booked = await self.db.appointments.find({"appointment_datetime": {"$gte": target.replace(hour=0), "$lte": target.replace(hour=23, minute=59)}, "status": {"$nin": ["cancelled"]}}).to_list(100)
        booked_times = {a["appointment_datetime"].strftime("%H:%M") for a in booked}
        available = [{"time": f"{h:02d}:{m:02d}"} for h in range(9, 17) for m in [0, 30] if f"{h:02d}:{m:02d}" not in booked_times]
        return {"date": date_str, "available_slots": available}
    
    async def _book_appointment(self, business_id: str, params: Dict, ip: str) -> Dict:
        import secrets
        appt_dt = datetime.fromisoformat(params.get("start_time").replace('Z', '+00:00'))
        appt_id = f"appt_{secrets.token_hex(8)}"
        await self.db.appointments.insert_one({"appointment_id": appt_id, "customer_email": params.get("attendee_email"), "appointment_type_name": params.get("title"), "appointment_datetime": appt_dt, "duration_minutes": params.get("duration_minutes", 30), "status": "scheduled", "business_id": business_id})
        
        meet_link = None
        try:
            from services.aurem_commercial import get_token_vault, IntegrationProvider
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import os
            
            vault = get_token_vault(self.db)
            token = await vault.get_credentials(business_id, IntegrationProvider.GOOGLE, "calendar", ip)
            if token:
                creds = Credentials(token=token["credentials"]["access_token"], refresh_token=token["credentials"].get("refresh_token"), token_uri="https://oauth2.googleapis.com/token", client_id=os.environ.get("GOOGLE_CLIENT_ID"), client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"))
                svc = build('calendar', 'v3', credentials=creds)
                end = (appt_dt + timedelta(minutes=30)).isoformat()
                evt = svc.events().insert(calendarId='primary', body={'summary': params.get("title"), 'start': {'dateTime': params.get("start_time")}, 'end': {'dateTime': end}, 'attendees': [{'email': params.get("attendee_email")}], 'conferenceData': {'createRequest': {'requestId': appt_id, 'conferenceSolutionKey': {'type': 'hangoutsMeet'}}}}, conferenceDataVersion=1, sendUpdates='all').execute()
                for ep in evt.get('conferenceData', {}).get('entryPoints', []):
                    if ep.get('entryPointType') == 'video':
                        meet_link = ep.get('uri')
        except Exception as e:
            logger.warning(f"Calendar failed: {e}")
        
        return {"appointment_id": appt_id, "title": params.get("title"), "attendee": params.get("attendee_email"), "meet_link": meet_link}
    
    async def _create_invoice(self, business_id: str, params: Dict) -> Dict:
        import stripe, os
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        if not stripe.api_key:
            raise Exception("Stripe not configured")
        
        custs = stripe.Customer.list(email=params.get("customer_email"), limit=1)
        cust = custs.data[0] if custs.data else stripe.Customer.create(email=params.get("customer_email"), metadata={"business_id": business_id})
        
        inv = stripe.Invoice.create(customer=cust.id, collection_method='send_invoice', days_until_due=7)
        total = 0
        for item in params.get("items", []):
            amt = int(item.get("amount", 0) * 100)
            stripe.InvoiceItem.create(customer=cust.id, invoice=inv.id, description=item.get("description"), unit_amount=amt, currency="cad")
            total += amt
        
        final = stripe.Invoice.finalize_invoice(inv.id)
        stripe.Invoice.send_invoice(inv.id)
        return {"invoice_id": final.id, "amount": total/100, "url": final.hosted_invoice_url}
    
    async def _create_payment_link(self, business_id: str, params: Dict) -> Dict:
        import stripe, os
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
        if not stripe.api_key:
            raise Exception("Stripe not configured")
        
        price = stripe.Price.create(product_data={"name": params.get("product_name")}, unit_amount=int(params.get("amount", 0) * 100), currency="cad")
        link = stripe.PaymentLink.create(line_items=[{"price": price.id, "quantity": 1}])
        return {"url": link.url, "amount": params.get("amount")}
    
    async def _send_email(self, business_id: str, params: Dict, ip: str) -> Dict:
        from services.aurem_commercial import get_gmail_service
        gmail = get_gmail_service(self.db)
        result = await gmail.send_email(business_id, params.get("to"), params.get("subject"), params.get("body"), ip_address=ip)
        if "error" in result:
            raise Exception(result["error"])
        return {"to": params.get("to"), "sent": True}
    
    async def _send_whatsapp(self, params: Dict) -> Dict:
        import os
        from twilio.rest import Client
        sid, token, from_num = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN"), os.environ.get("TWILIO_WHATSAPP_FROM")
        if not sid:
            raise Exception("Twilio not configured")
        client = Client(sid, token)
        phone = params.get("phone")
        msg = client.messages.create(body=params.get("message"), from_=f"whatsapp:{from_num}", to=f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone)
        return {"sid": msg.sid, "to": phone, "sent": True}
    
    async def handle_tool_call(self, business_id: str, func: str, args: Dict, ip: str = None) -> Dict:
        mapping = {"check_calendar_availability": ActionType.CALENDAR_CHECK, "book_appointment": ActionType.CALENDAR_BOOK, "create_invoice": ActionType.STRIPE_INVOICE, "create_payment_link": ActionType.STRIPE_LINK, "send_email": ActionType.EMAIL_SEND, "send_whatsapp": ActionType.WHATSAPP_SEND}
        action_type = mapping.get(func)
        if not action_type:
            return {"error": f"Unknown: {func}"}
        result = await self.execute(business_id, action_type, args, "ai_brain", ip)
        return {"action_id": result.action_id, "status": result.status.value, "result": result.result, "error": result.error}


_action_engine = None

def get_action_engine(db) -> ActionEngine:
    global _action_engine
    if _action_engine is None:
        _action_engine = ActionEngine(db)
    return _action_engine
