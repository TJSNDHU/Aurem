"""
Stripe webhook alias — exposes /api/stripe/webhook as a thin pass-through
to the canonical handler at /api/payments/webhook/stripe.

Why?
  Production Stripe destination (we_1TRL2p2XYZ7cJIy2MtZd2JcN, "aurem-automation")
  was configured by the user with endpoint URL https://aurem.live/api/stripe/webhook.
  The existing handler lives at /api/payments/webhook/stripe (organic name from
  early router design). Rather than ask the user to reconfigure Stripe (and
  risk breaking signed-URL secrets), we register a single-line alias that
  delegates to the canonical handler — preserving signature verification,
  idempotency, subscription activation, and all event handling that's already
  battle-tested. iter 280.13
"""
from fastapi import APIRouter, Request

from routers.stripe_payment_router import stripe_webhook as _canonical_stripe_webhook

router = APIRouter(tags=["Stripe Webhook (alias)"])


@router.post("/api/stripe/webhook")
async def stripe_webhook_alias(request: Request):
    return await _canonical_stripe_webhook(request)
