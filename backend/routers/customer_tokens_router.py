"""
Customer Token Wallet — P1 #2 Website Editor Tokens
====================================================
Endpoints:
    GET  /api/customer/tokens                 -- current balance + transaction history
    POST /api/customer/tokens/spend            -- deduct tokens for an action (requires auth)
    POST /api/customer/tokens/purchase/intent  -- create Stripe Payment Intent for token pack

Costs:
    new_page        = 2
    new_section     = 3
    design_change   = 5
    full_redesign   = 10
Price: 10 tokens = $19 CAD (never expire).
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/tokens", tags=["Customer Tokens"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

TOKEN_COSTS = {
    "new_page": 2,
    "new_section": 3,
    "design_change": 5,
    "full_redesign": 10,
}

TOKEN_PACK_CENTS = 1900  # $19.00 CAD
TOKEN_PACK_SIZE = 10

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "Database not available")
    return _db


async def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _get_email(payload: dict) -> str:
    em = (payload.get("email") or payload.get("sub") or "").lower()
    if not em:
        raise HTTPException(401, "Invalid token")
    return em


@router.get("")
async def get_balance(request: Request):
    payload = await _auth(request)
    db = _get_db()
    email = await _get_email(payload)

    wallet = await db.customer_token_wallets.find_one({"email": email}, {"_id": 0}) or {}
    balance = int(wallet.get("balance", 0))

    tx_cursor = db.customer_token_transactions.find(
        {"email": email}, {"_id": 0}
    ).sort("created_at", -1).limit(20)
    transactions = [t async for t in tx_cursor]

    return {
        "balance": balance,
        "costs": TOKEN_COSTS,
        "pack": {"tokens": TOKEN_PACK_SIZE, "price_cents": TOKEN_PACK_CENTS, "currency": "CAD"},
        "transactions": transactions,
    }


class SpendRequest(BaseModel):
    action: str = Field(..., description="new_page | new_section | design_change | full_redesign")
    memo: Optional[str] = None


@router.post("/spend")
async def spend_tokens(body: SpendRequest, request: Request):
    payload = await _auth(request)
    db = _get_db()
    email = await _get_email(payload)

    cost = TOKEN_COSTS.get(body.action)
    if not cost:
        raise HTTPException(400, f"Unknown action: {body.action}")

    wallet = await db.customer_token_wallets.find_one({"email": email}, {"_id": 0}) or {"balance": 0}
    if int(wallet.get("balance", 0)) < cost:
        raise HTTPException(402, f"Insufficient tokens. Need {cost}, have {wallet.get('balance', 0)}.")

    now = datetime.now(timezone.utc).isoformat()
    await db.customer_token_wallets.update_one(
        {"email": email},
        {"$inc": {"balance": -cost}, "$set": {"updated_at": now}},
        upsert=True,
    )
    await db.customer_token_transactions.insert_one({
        "email": email,
        "type": "spend",
        "action": body.action,
        "amount": -cost,
        "memo": body.memo or "",
        "created_at": now,
    })
    # Queue the actual work item
    await db.customer_edit_requests.insert_one({
        "email": email,
        "action": body.action,
        "memo": body.memo or "",
        "tokens_spent": cost,
        "status": "queued",
        "created_at": now,
    })

    new_balance = await db.customer_token_wallets.find_one({"email": email}, {"_id": 0, "balance": 1})
    return {"success": True, "spent": cost, "balance": int(new_balance.get("balance", 0)), "action": body.action}


@router.post("/purchase/intent")
async def create_purchase_intent(request: Request):
    """Create a Stripe PaymentIntent for a token pack. On webhook success,
    webhook handler credits the wallet via credit_tokens()."""
    payload = await _auth(request)
    _get_db()  # ensure DB connection available
    email = await _get_email(payload)

    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
        intent = stripe.PaymentIntent.create(
            amount=TOKEN_PACK_CENTS,
            currency="cad",
            automatic_payment_methods={"enabled": True},
            metadata={
                "purpose": "aurem_token_pack",
                "email": email,
                "tokens": str(TOKEN_PACK_SIZE),
            },
        )
        return {
            "client_secret": intent.client_secret,
            "amount": TOKEN_PACK_CENTS,
            "tokens": TOKEN_PACK_SIZE,
            "currency": "CAD",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TOKENS] Stripe error: {e}")
        raise HTTPException(502, "Unable to create payment intent")


async def credit_tokens(email: str, tokens: int, payment_intent_id: str = "") -> int:
    """Public helper called by the Stripe webhook handler after successful payment."""
    if _db is None:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    await _db.customer_token_wallets.update_one(
        {"email": email.lower()},
        {"$inc": {"balance": int(tokens)}, "$set": {"updated_at": now}},
        upsert=True,
    )
    await _db.customer_token_transactions.insert_one({
        "email": email.lower(),
        "type": "credit",
        "amount": int(tokens),
        "payment_intent_id": payment_intent_id,
        "created_at": now,
    })
    w = await _db.customer_token_wallets.find_one({"email": email.lower()}, {"_id": 0, "balance": 1})
    return int((w or {}).get("balance", 0))
