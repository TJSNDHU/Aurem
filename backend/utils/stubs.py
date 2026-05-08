"""
Stub implementations for functions referenced but not yet implemented.
Each stub logs a warning and returns None to prevent runtime crashes.
Replace with real implementations as features are built out.
"""
import logging

logger = logging.getLogger("aurem.stubs")


# ============= EMAIL STUBS =============

async def send_newsletter_confirmation_email(email: str, message: str):
    logger.warning(f"send_newsletter_confirmation_email not implemented — skipping (to={email})")
    return None


async def send_sms_notification(phone: str, message: str):
    logger.warning(f"send_sms_notification not implemented — skipping (to={phone[:7]}***)")
    return None


async def send_shipping_update_email(order: dict, email: str, status: str):
    logger.warning(f"send_shipping_update_email not implemented — skipping (to={email}, status={status})")
    return None


async def send_review_notification_email(review: dict, product_name: str, customer_name: str, email: str):
    logger.warning(f"send_review_notification_email not implemented — skipping (to={email})")
    return None


async def send_oroe_vip_approval_email(email: str, first_name: str, access_code: str, bottle_number: int, reservation_expires: str):
    logger.warning(f"send_oroe_vip_approval_email not implemented — skipping (to={email})")
    return None


async def send_milestone_almost_there_email(*args, **kwargs):
    logger.warning("send_milestone_almost_there_email not implemented — skipping")
    return None


async def send_partner_approved_whatsapp(*args, **kwargs):
    logger.warning("send_partner_approved_whatsapp not implemented — skipping")
    return None


async def send_partner_denied_whatsapp(*args, **kwargs):
    logger.warning("send_partner_denied_whatsapp not implemented — skipping")
    return None


async def send_goal_achieved_email(*args, **kwargs):
    logger.warning("send_goal_achieved_email not implemented — skipping")
    return None


# ============= SHIPPING/LOGISTICS STUBS =============

async def handle_flagship_webhook(db, payload: dict):
    logger.warning("handle_flagship_webhook not implemented — skipping")
    return {"status": "skipped", "message": "Flagship webhook handler not implemented"}


async def calculate_shipping_rates(*args, **kwargs):
    logger.warning("calculate_shipping_rates not implemented — skipping")
    return []


async def calculate_landed_cost(*args, **kwargs):
    logger.warning("calculate_landed_cost not implemented — skipping")
    return {"total": 0, "duties": 0, "taxes": 0}


# ============= CRM/CUSTOMER STUBS =============

async def get_all_customers_summary(filters=None):
    logger.warning("get_all_customers_summary not implemented — skipping")
    return []


async def get_customer_full_record(email: str):
    logger.warning(f"get_customer_full_record not implemented — skipping (email={email})")
    return None


async def update_customer_notes(email: str, notes: str):
    logger.warning(f"update_customer_notes not implemented — skipping (email={email})")
    return False


async def request_refund(order_id: str, customer_email: str, reason: str, refund_type: str, photos=None):
    logger.warning(f"request_refund not implemented — skipping (order={order_id})")
    return {"status": "skipped", "message": "Refund handler not implemented"}


async def get_refunds(status: str = None):
    logger.warning("get_refunds not implemented — skipping")
    return []


async def resolve_refund(refund_id: str, action: str, admin_name: str, notes: str = None, partial_amount: float = None):
    logger.warning(f"resolve_refund not implemented — skipping (refund={refund_id})")
    return {"status": "skipped", "message": "Refund resolver not implemented"}


async def get_sales_dashboard(period: str = "30d"):
    logger.warning("get_sales_dashboard not implemented — skipping")
    return {"total_revenue": 0, "total_orders": 0, "period": period}


async def get_acquisition_sources():
    logger.warning("get_acquisition_sources not implemented — skipping")
    return []


async def get_revenue_metrics():
    logger.warning("get_revenue_metrics not implemented — skipping")
    return {"mrr": 0, "arr": 0, "growth": 0}


# ============= LOYALTY/REFERRAL STUBS =============

async def mark_restock_conversion(*args, **kwargs):
    logger.warning("mark_restock_conversion not implemented — skipping")
    return None


async def verify_referral_for_milestone(*args, **kwargs):
    logger.warning("verify_referral_for_milestone not implemented — skipping")
    return None


# ============= IMAGE/CLEANUP STUBS =============

async def cleanup_broken_images():
    logger.warning("cleanup_broken_images not implemented — skipping")
    return None


# ============= CONSTANTS =============

POINTS_PER_PRODUCT = 250
MILESTONE_REFERRAL_THRESHOLD = 10
MILESTONE_EMAIL_TRIGGER = 8
MILESTONE_DISCOUNT_PERCENT = 20
