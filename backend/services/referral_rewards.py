"""
Referral Reward Automation — P1 #6
===================================
Stripe webhook → if subscription belongs to a user referred via ?ref=BIN,
apply 1-month free coupon to the REFERRER's subscription + mark referral as subscribed.

Called from the existing Stripe webhook handler when event.type == 'customer.subscription.created'
or 'checkout.session.completed'.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Coupon ID must be pre-created in Stripe dashboard (30-day 100%-off coupon)
AUREM_REFERRAL_COUPON_ID = os.environ.get("STRIPE_REFERRAL_COUPON_ID", "aurem_referral_1mo_free")


async def handle_new_subscription(db, referee_email: str, stripe_subscription_id: str) -> Optional[str]:
    """If this email was referred, flip referral status + apply coupon to the REFERRER."""
    if not referee_email:
        return None
    referee_email = referee_email.lower()

    ref = await db.referrals.find_one(
        {"referee_email": referee_email, "status": {"$in": ["pending", "signed_up"]}},
        {"_id": 0},
    )
    if not ref:
        return None

    referrer_email = ref.get("referrer_email", "").lower()
    if not referrer_email:
        return None

    # Update referral doc
    now = datetime.now(timezone.utc).isoformat()
    await db.referrals.update_one(
        {"referee_email": referee_email, "referrer_email": referrer_email},
        {"$set": {"status": "subscribed", "subscribed_at": now, "referee_subscription_id": stripe_subscription_id}},
    )

    # Apply coupon to referrer's active subscription
    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

        referrer = await db.platform_users.find_one({"email": referrer_email}, {"_id": 0, "stripe_customer_id": 1, "stripe_subscription_id": 1}) \
            or await db.users.find_one({"email": referrer_email}, {"_id": 0, "stripe_customer_id": 1, "stripe_subscription_id": 1})
        if not referrer:
            logger.info(f"[REFERRAL] No user doc found for referrer {referrer_email}")
            return None

        sub_id = referrer.get("stripe_subscription_id")
        if sub_id and AUREM_REFERRAL_COUPON_ID:
            stripe.Subscription.modify(sub_id, coupon=AUREM_REFERRAL_COUPON_ID)
            await db.referrals.update_one(
                {"referee_email": referee_email, "referrer_email": referrer_email},
                {"$set": {"coupon_applied": AUREM_REFERRAL_COUPON_ID, "coupon_applied_at": now}},
            )
            logger.info(f"[REFERRAL] Applied {AUREM_REFERRAL_COUPON_ID} to {referrer_email} sub {sub_id}")

        # Notify referrer via WhatsApp if we can
        try:
            from routers.whatsapp_alerts import send_whatsapp
            phone = (referrer.get("phone") or "").strip() if referrer else ""
            if phone:
                await send_whatsapp(phone, "🎉 Reward unlocked! Your referral just subscribed — 1 month free applied to your next AUREM invoice.")
        except Exception as e:
            logger.debug(f"[REFERRAL] Notify failed: {e}")

        return referrer_email
    except Exception as e:
        logger.error(f"[REFERRAL] Coupon apply failed: {e}")
        return referrer_email  # still credited in DB
