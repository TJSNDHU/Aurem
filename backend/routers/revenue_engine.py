"""
Phase E: Revenue Automation Engine
MRR/ARR metrics, usage metering, invoice management, payment history
"""
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List
import jwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/revenue", tags=["Revenue Engine"])

from config import JWT_SECRET
JWT_ALGORITHM = "HS256"

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

async def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


# ─── Revenue Dashboard Metrics ───────────────────────────────────────

@router.get("/dashboard")
async def revenue_dashboard(request: Request):
    """Aggregated revenue metrics: MRR, ARR, churn, LTV, growth"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month = (month_start - timedelta(days=1)).replace(day=1)

    # Count active subscriptions
    total_subs = await db.subscriptions.count_documents({"tenant_id": tenant_id, "status": "active"})
    churned = await db.subscriptions.count_documents({
        "tenant_id": tenant_id, "status": "canceled",
        "canceled_at": {"$gte": month_start.isoformat()}
    })

    # Revenue from payments collection
    pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": "paid", "created_at": {"$gte": month_start.isoformat()}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    agg = await db.payments.aggregate(pipeline).to_list(1)
    current_mrr = agg[0]["total"] if agg else 0

    prev_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": "paid",
                     "created_at": {"$gte": prev_month.isoformat(), "$lt": month_start.isoformat()}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    prev_agg = await db.payments.aggregate(prev_pipeline).to_list(1)
    prev_mrr = prev_agg[0]["total"] if prev_agg else 0

    growth_pct = round(((current_mrr - prev_mrr) / prev_mrr * 100), 1) if prev_mrr > 0 else 0
    churn_rate = round((churned / total_subs * 100), 1) if total_subs > 0 else 0
    ltv = round(current_mrr / (churn_rate / 100), 2) if churn_rate > 0 else round(current_mrr * 24, 2)

    # Daily revenue for chart (last 30 days)
    daily_pipeline = [
        {"$match": {"tenant_id": tenant_id, "status": "paid",
                     "created_at": {"$gte": (now - timedelta(days=30)).isoformat()}}},
        {"$group": {"_id": {"$substr": ["$created_at", 0, 10]}, "amount": {"$sum": "$amount"}}},
        {"$sort": {"_id": 1}}
    ]
    daily_data = await db.payments.aggregate(daily_pipeline).to_list(31)
    daily_revenue = [{"date": d["_id"], "amount": d["amount"]} for d in daily_data]

    return {
        "mrr": current_mrr,
        "arr": round(current_mrr * 12, 2),
        "growth_pct": growth_pct,
        "churn_rate": churn_rate,
        "ltv": ltv,
        "active_subscriptions": total_subs,
        "churned_this_month": churned,
        "prev_mrr": prev_mrr,
        "daily_revenue": daily_revenue,
        "period": {"start": month_start.isoformat(), "end": now.isoformat()}
    }


# ─── Usage Metering ──────────────────────────────────────────────────

class UsageEvent(BaseModel):
    event_type: str = Field(..., description="ai_message|api_call|storage|email|sms")
    quantity: int = 1
    metadata: Optional[dict] = None

@router.post("/usage/track")
async def track_usage(event: UsageEvent, request: Request):
    """Record a usage event for metering"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    record = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "user_id": user.get("user_id"),
        "event_type": event.event_type,
        "quantity": event.quantity,
        "metadata": event.metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.usage_events.insert_one(record)
    return {"tracked": True, "event_id": record["id"]}

@router.get("/usage/summary")
async def usage_summary(request: Request):
    """Get usage summary for current billing period"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pipeline = [
        {"$match": {"tenant_id": tenant_id, "created_at": {"$gte": month_start.isoformat()}}},
        {"$group": {"_id": "$event_type", "count": {"$sum": "$quantity"}}}
    ]
    results = await db.usage_events.aggregate(pipeline).to_list(20)
    usage = {r["_id"]: r["count"] for r in results}

    # Determine plan limits
    sub = await db.subscriptions.find_one({"tenant_id": tenant_id, "status": "active"}, {"_id": 0})
    plan = sub.get("plan", "trial") if sub else "trial"
    limits = {
        "trial": {"ai_messages": 500, "api_calls": 1000, "emails": 50, "storage_mb": 100},
        "starter": {"ai_messages": 5000, "api_calls": 10000, "emails": 500, "storage_mb": 1000},
        "pro": {"ai_messages": 25000, "api_calls": 50000, "emails": 5000, "storage_mb": 10000},
        "enterprise": {"ai_messages": 999999, "api_calls": 999999, "emails": 999999, "storage_mb": 999999}
    }.get(plan, {"ai_messages": 500, "api_calls": 1000, "emails": 50, "storage_mb": 100})

    # Daily breakdown for chart
    daily_pipeline = [
        {"$match": {"tenant_id": tenant_id, "created_at": {"$gte": (now - timedelta(days=14)).isoformat()}}},
        {"$group": {
            "_id": {"date": {"$substr": ["$created_at", 0, 10]}, "type": "$event_type"},
            "count": {"$sum": "$quantity"}
        }},
        {"$sort": {"_id.date": 1}}
    ]
    daily_raw = await db.usage_events.aggregate(daily_pipeline).to_list(200)
    daily_usage = {}
    for d in daily_raw:
        date = d["_id"]["date"]
        if date not in daily_usage:
            daily_usage[date] = {}
        daily_usage[date][d["_id"]["type"]] = d["count"]

    return {
        "plan": plan,
        "period": {"start": month_start.isoformat(), "end": now.isoformat()},
        "usage": usage,
        "limits": limits,
        "daily_breakdown": daily_usage
    }


# ─── Invoices ────────────────────────────────────────────────────────

class LineItem(BaseModel):
    description: str
    quantity: float = 1
    unit_price: float
    amount: Optional[float] = None

class InvoiceCreate(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    line_items: List[LineItem]
    tax_rate: float = 0  # percentage
    payment_method: str = "e_transfer"  # e_transfer, cheque, cash, stripe
    payment_instructions: Optional[str] = None
    due_days: int = 30
    notes: Optional[str] = None
    currency: str = "CAD"

class InvoiceStatusUpdate(BaseModel):
    status: str  # draft, sent, awaiting_payment, paid, overdue, cancelled

class PaymentRecord(BaseModel):
    payment_method: str  # e_transfer, cheque, cash, stripe
    amount: Optional[float] = None
    reference: Optional[str] = None  # cheque #, e-transfer ref, Stripe ID
    notes: Optional[str] = None


@router.get("/invoices")
async def list_invoices(request: Request, limit: int = 20, skip: int = 0, status: Optional[str] = None):
    """List invoices with optional status filter"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    query = {"tenant_id": tenant_id}
    if status:
        query["status"] = status

    invoices = await db.invoices.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.invoices.count_documents(query)

    # Calculate summary
    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$total"}
        }}
    ]
    summary_data = await db.invoices.aggregate(pipeline).to_list(20)
    summary = {item["_id"]: {"count": item["count"], "amount": item["total_amount"]} for item in summary_data}

    return {"invoices": invoices, "total": total, "summary": summary}


@router.post("/invoices")
async def create_invoice(invoice: InvoiceCreate, request: Request):
    """Create a new invoice for a customer"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    now = datetime.now(timezone.utc)
    inv_number = f"INV-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

    # Calculate line items
    items = []
    subtotal = 0
    for item in invoice.line_items:
        amt = round(item.quantity * item.unit_price, 2)
        items.append({
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "amount": amt,
        })
        subtotal += amt

    tax_amount = round(subtotal * (invoice.tax_rate / 100), 2)
    total = round(subtotal + tax_amount, 2)
    due_date = (now + timedelta(days=invoice.due_days)).isoformat()

    # Payment instructions based on method
    pay_instructions = invoice.payment_instructions
    if not pay_instructions:
        if invoice.payment_method == "e_transfer":
            pay_instructions = "Send e-Transfer to the email on file. Use invoice number as reference."
        elif invoice.payment_method == "cheque":
            pay_instructions = "Make cheque payable to business name. Mail to address on file."
        elif invoice.payment_method == "cash":
            pay_instructions = "Cash payment accepted in person at our location."
        else:
            pay_instructions = "Payment instructions will be provided."

    doc = {
        "id": str(uuid.uuid4()),
        "invoice_number": inv_number,
        "tenant_id": tenant_id,
        "customer_name": invoice.customer_name,
        "customer_email": invoice.customer_email,
        "customer_phone": invoice.customer_phone,
        "line_items": items,
        "subtotal": subtotal,
        "tax_rate": invoice.tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "currency": invoice.currency,
        "payment_method": invoice.payment_method,
        "payment_instructions": pay_instructions,
        "status": "draft",
        "due_date": due_date,
        "due_days": invoice.due_days,
        "notes": invoice.notes,
        "payments": [],
        "amount_paid": 0,
        "amount_due": total,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": user.get("email", ""),
    }

    await db.invoices.insert_one(doc)
    doc.pop("_id", None)

    return {"success": True, "invoice": doc}


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, request: Request):
    """Get single invoice detail"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one(
        {"id": invoice_id, "tenant_id": tenant_id}, {"_id": 0}
    )
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return inv


@router.put("/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, update: InvoiceStatusUpdate, request: Request):
    """Update invoice status (send, cancel, mark overdue)"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    valid_statuses = ["draft", "sent", "awaiting_payment", "paid", "overdue", "cancelled"]
    if update.status not in valid_statuses:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")

    result = await db.invoices.update_one(
        {"id": invoice_id, "tenant_id": tenant_id},
        {"$set": {"status": update.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    if result.matched_count == 0:
        raise HTTPException(404, "Invoice not found")

    return {"success": True, "invoice_id": invoice_id, "status": update.status}


@router.post("/invoices/{invoice_id}/payment")
async def record_payment(invoice_id: str, payment: PaymentRecord, request: Request):
    """Record a payment against an invoice (cheque, e-transfer, cash, etc.)"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")

    pay_amount = payment.amount or inv.get("amount_due", inv.get("total", 0))
    now = datetime.now(timezone.utc)

    payment_record = {
        "id": str(uuid.uuid4()),
        "amount": pay_amount,
        "method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "recorded_by": user.get("email", ""),
        "recorded_at": now.isoformat(),
    }

    new_paid = inv.get("amount_paid", 0) + pay_amount
    new_due = max(inv.get("total", 0) - new_paid, 0)
    new_status = "paid" if new_due <= 0 else inv.get("status", "awaiting_payment")

    await db.invoices.update_one(
        {"id": invoice_id, "tenant_id": tenant_id},
        {
            "$push": {"payments": payment_record},
            "$set": {
                "amount_paid": round(new_paid, 2),
                "amount_due": round(new_due, 2),
                "status": new_status,
                "updated_at": now.isoformat(),
            }
        }
    )

    # Also record in payments collection for revenue tracking
    await db.payments.insert_one({
        "id": payment_record["id"],
        "tenant_id": tenant_id,
        "invoice_id": invoice_id,
        "amount": pay_amount,
        "method": payment.payment_method,
        "reference": payment.reference,
        "status": "completed",
        "created_at": now.isoformat(),
    })

    return {
        "success": True,
        "payment": payment_record,
        "invoice_status": new_status,
        "amount_paid": round(new_paid, 2),
        "amount_due": round(new_due, 2),
    }


@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, request: Request):
    """Delete a draft invoice"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.get("status") not in ["draft", "cancelled"]:
        raise HTTPException(400, "Only draft or cancelled invoices can be deleted")

    await db.invoices.delete_one({"id": invoice_id, "tenant_id": tenant_id})
    return {"success": True, "deleted": invoice_id}


# ─── Payments ────────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(request: Request, limit: int = 20, skip: int = 0):
    """List payment history"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    payments = await db.payments.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    total = await db.payments.count_documents({"tenant_id": tenant_id})
    return {"payments": payments, "total": total}


# ─── Revenue Forecast ────────────────────────────────────────────────

@router.get("/forecast")
async def revenue_forecast(request: Request):
    """Simple linear forecast for next 3 months"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    now = datetime.now(timezone.utc)
    months = []
    for i in range(6):
        m = (now - timedelta(days=30 * i)).replace(day=1)
        m_end = (m + timedelta(days=32)).replace(day=1)
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "status": "paid",
                         "created_at": {"$gte": m.isoformat(), "$lt": m_end.isoformat()}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        agg = await db.payments.aggregate(pipeline).to_list(1)
        months.append({"month": m.strftime("%Y-%m"), "revenue": agg[0]["total"] if agg else 0})

    months.reverse()
    if len(months) >= 2:
        trend = (months[-1]["revenue"] - months[0]["revenue"]) / max(len(months) - 1, 1)
    else:
        trend = 0

    forecast = []
    last_rev = months[-1]["revenue"] if months else 0
    for i in range(1, 4):
        fm = (now + timedelta(days=30 * i)).strftime("%Y-%m")
        forecast.append({"month": fm, "projected": round(max(last_rev + trend * i, 0), 2)})

    return {"historical": months, "forecast": forecast, "monthly_trend": round(trend, 2)}



# ═══════════════════════════════════════════════════════════════
# INVOICE PDF GENERATION
# ═══════════════════════════════════════════════════════════════

@router.get("/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, request: Request):
    """Generate and download invoice as PDF"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")

    inv.pop("_id", None)

    settings = await db.tenant_settings.find_one({"tenant_id": tenant_id})
    business_info = {}
    if settings:
        business_info = {
            "name": settings.get("business_name", ""),
            "email": settings.get("email", ""),
            "phone": settings.get("phone", ""),
            "address": settings.get("address", ""),
        }

    from services.invoice_pdf_service import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(inv, business_info)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={inv.get('invoice_number', 'invoice')}.pdf"
        }
    )


@router.get("/invoices/{invoice_id}/share")
async def get_invoice_share_link(invoice_id: str, request: Request):
    """Generate a shareable link for an invoice"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")

    share_token = str(uuid.uuid4())
    await db.invoices.update_one(
        {"id": invoice_id},
        {"$set": {"share_token": share_token, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    host = request.headers.get("host", "localhost")
    proto = request.headers.get("x-forwarded-proto", "https")
    share_url = f"{proto}://{host}/api/revenue/public/invoice/{share_token}"

    return {"share_url": share_url, "share_token": share_token}


@router.get("/public/invoice/{share_token}")
async def view_public_invoice(share_token: str):
    """Public invoice view (no auth) — returns PDF"""
    db = get_db()
    inv = await db.invoices.find_one({"share_token": share_token})
    if not inv:
        raise HTTPException(404, "Invoice not found or link expired")

    inv.pop("_id", None)

    from services.invoice_pdf_service import generate_invoice_pdf
    pdf_bytes = generate_invoice_pdf(inv)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={inv.get('invoice_number', 'invoice')}.pdf"
        }
    )


# ═══════════════════════════════════════════════════════════════
# AUTO-INVOICE FROM PIPELINE DEALS
# ═══════════════════════════════════════════════════════════════

class AutoInvoiceRequest(BaseModel):
    deal_name: str
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: float
    description: Optional[str] = None
    payment_method: str = "e_transfer"
    tax_rate: float = 13
    due_days: int = 30
    deal_id: Optional[str] = None


@router.post("/auto-invoice")
async def auto_invoice_from_deal(req: AutoInvoiceRequest, request: Request):
    """Auto-create an invoice when a deal is closed/won"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    now = datetime.now(timezone.utc)
    inv_number = f"INV-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

    description = req.description or f"Services for: {req.deal_name}"
    subtotal = round(req.amount, 2)
    tax_amount = round(subtotal * (req.tax_rate / 100), 2)
    total = round(subtotal + tax_amount, 2)
    due_date = (now + timedelta(days=req.due_days)).isoformat()

    pay_instructions = ""
    if req.payment_method == "e_transfer":
        pay_instructions = "Send e-Transfer to the email on file. Use invoice number as reference."
    elif req.payment_method == "cheque":
        pay_instructions = "Make cheque payable to business name. Mail to address on file."
    elif req.payment_method == "cash":
        pay_instructions = "Cash payment accepted in person."

    doc = {
        "id": str(uuid.uuid4()),
        "invoice_number": inv_number,
        "tenant_id": tenant_id,
        "customer_name": req.customer_name,
        "customer_email": req.customer_email,
        "customer_phone": req.customer_phone,
        "line_items": [{"description": description, "quantity": 1, "unit_price": subtotal, "amount": subtotal}],
        "subtotal": subtotal,
        "tax_rate": req.tax_rate,
        "tax_amount": tax_amount,
        "total": total,
        "currency": "CAD",
        "payment_method": req.payment_method,
        "payment_instructions": pay_instructions,
        "status": "sent",
        "due_date": due_date,
        "due_days": req.due_days,
        "notes": f"Auto-generated from deal: {req.deal_name}",
        "payments": [],
        "amount_paid": 0,
        "amount_due": total,
        "auto_generated": True,
        "source_deal_id": req.deal_id,
        "source_deal_name": req.deal_name,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "created_by": user.get("email", ""),
    }

    await db.invoices.insert_one(doc)
    doc.pop("_id", None)

    return {"success": True, "invoice": doc}


# ═══════════════════════════════════════════════════════════════
# PAYMENT REMINDER AUTOMATION
# ═══════════════════════════════════════════════════════════════

@router.get("/reminders")
async def get_overdue_invoices(request: Request):
    """Get all overdue invoices that need payment reminders"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))
    now = datetime.now(timezone.utc).isoformat()

    overdue_query = {
        "tenant_id": tenant_id,
        "status": {"$in": ["sent", "awaiting_payment"]},
        "due_date": {"$lt": now},
    }

    overdue = await db.invoices.find(overdue_query, {"_id": 0}).sort("due_date", 1).to_list(50)

    if overdue:
        ids = [inv["id"] for inv in overdue]
        await db.invoices.update_many(
            {"id": {"$in": ids}},
            {"$set": {"status": "overdue", "updated_at": now}}
        )
        for inv in overdue:
            inv["status"] = "overdue"

    three_days = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    approaching_query = {
        "tenant_id": tenant_id,
        "status": {"$in": ["sent", "awaiting_payment"]},
        "due_date": {"$gte": now, "$lte": three_days},
    }
    approaching = await db.invoices.find(approaching_query, {"_id": 0}).sort("due_date", 1).to_list(50)

    return {
        "overdue": overdue,
        "overdue_count": len(overdue),
        "overdue_total": sum(inv.get("amount_due", 0) for inv in overdue),
        "approaching_due": approaching,
        "approaching_count": len(approaching),
        "approaching_total": sum(inv.get("amount_due", 0) for inv in approaching),
    }


@router.post("/reminders/send/{invoice_id}")
async def send_payment_reminder(invoice_id: str, request: Request):
    """Send a payment reminder for an overdue invoice"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    inv = await db.invoices.find_one({"id": invoice_id, "tenant_id": tenant_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")

    now = datetime.now(timezone.utc)

    reminder = {
        "id": str(uuid.uuid4()),
        "type": "payment_reminder",
        "invoice_id": invoice_id,
        "invoice_number": inv.get("invoice_number"),
        "customer_name": inv.get("customer_name"),
        "customer_email": inv.get("customer_email"),
        "amount_due": inv.get("amount_due", inv.get("total", 0)),
        "due_date": inv.get("due_date"),
        "sent_at": now.isoformat(),
        "sent_by": user.get("email", ""),
        "method": "email" if inv.get("customer_email") else "manual",
        "status": "sent",
    }

    await db.payment_reminders.insert_one(reminder)
    reminder.pop("_id", None)

    await db.invoices.update_one(
        {"id": invoice_id},
        {
            "$inc": {"reminder_count": 1},
            "$set": {"last_reminder_at": now.isoformat(), "updated_at": now.isoformat()}
        }
    )

    return {
        "success": True,
        "reminder": reminder,
        "note": "Reminder recorded. Email delivery activates with Resend API key."
    }


@router.get("/reminders/history")
async def reminder_history(request: Request, limit: int = 20):
    """Get payment reminder history"""
    user = await _get_user(request)
    db = get_db()

    reminders = await db.payment_reminders.find(
        {}, {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)

    return {"reminders": reminders, "total": len(reminders)}

print("[STARTUP] Revenue Engine loaded (Phase E: Revenue Automation)", flush=True)
