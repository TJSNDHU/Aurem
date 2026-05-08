"""
Stripe, Bambora, PayPal + connected accounts
Extracted from server.py during modularization.
"""

import os
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from utils.stubs import POINTS_PER_PRODUCT, send_review_notification_email
try:
    from models.server_models import (
        CallbackRequest, CheckoutRequest, PaymentTransaction, Review, ReviewCreate,
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
async def check_and_link_gift_to_order(*args, **kwargs): pass  # Stub
async def get_loyalty_config(*args, **kwargs): return {}  # Stub
async def deduct_inventory_for_order(*args, **kwargs): pass  # Stub
async def process_auto_shipping(*args, **kwargs): pass  # Stub
import base64
_paypal_token_cache = {'token': None, 'expires_at': 0}
async def get_paypal_access_token():
    import time
    if _paypal_token_cache['token'] and _paypal_token_cache['expires_at'] > time.time() + 60:
        return _paypal_token_cache['token']
    pid = os.environ.get('PAYPAL_CLIENT_ID', '')
    psecret = os.environ.get('PAYPAL_SECRET', '')
    if not pid or not psecret: raise Exception('PayPal not configured')
    creds = base64.b64encode(f'{pid}:{psecret}'.encode()).decode()
    pbase = 'https://api-m.sandbox.paypal.com' if os.environ.get('PAYPAL_MODE','sandbox')=='sandbox' else 'https://api-m.paypal.com'
    async with httpx.AsyncClient() as client:
        resp = await client.post(f'{pbase}/v1/oauth2/token', headers={'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}, data='grant_type=client_credentials')
        if resp.status_code == 200:
            data = resp.json()
            _paypal_token_cache['token'] = data['access_token']
            _paypal_token_cache['expires_at'] = time.time() + data.get('expires_in', 3600)
            return data['access_token']
        raise Exception(f'PayPal auth failed: {resp.status_code}')

_stripe_checkout = None
def get_stripe_checkout():
    global _stripe_checkout
    if _stripe_checkout is None:
        try:
            from emergentintegrations.payments.stripe.checkout import (
                StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
            )
            _stripe_checkout = {
                'StripeCheckout': StripeCheckout,
                'CheckoutSessionResponse': CheckoutSessionResponse,
                'CheckoutStatusResponse': CheckoutStatusResponse,
                'CheckoutSessionRequest': CheckoutSessionRequest
            }
        except ImportError:
            _stripe_checkout = {}
    return _stripe_checkout

_llm_chat = None
def get_llm_chat():
    global _llm_chat
    if _llm_chat is None:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            _llm_chat = {'LlmChat': LlmChat, 'UserMessage': UserMessage}
        except ImportError:
            _llm_chat = {}
    return _llm_chat
try:
    from services.email_templates import send_order_confirmation_email
except ImportError:
    async def send_order_confirmation_email(*args, **kwargs): pass
def get_claude_api_key():
    return os.environ.get('EMERGENT_LLM_KEY', '')
try:
    from middleware.websocket_manager import broadcast_admin_event
except ImportError:
    async def broadcast_admin_event(*args, **kwargs): pass
try:
    from utils.auth_utils import require_auth
except ImportError:
    try:
        from utils.auth import require_auth
    except ImportError:
        require_auth = None

# Environment variables
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

# Payment & messaging env vars
BAMBORA_MERCHANT_ID = os.environ.get('BAMBORA_MERCHANT_ID', '')
BAMBORA_API_PASSCODE = os.environ.get('BAMBORA_API_PASSCODE', '')
BAMBORA_API_URL = os.environ.get('BAMBORA_API_URL', 'https://api.na.bambora.com')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET', '')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')
PAYPAL_API_BASE = 'https://api-m.sandbox.paypal.com' if os.environ.get('PAYPAL_MODE', 'sandbox') == 'sandbox' else 'https://api-m.paypal.com'
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')


# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c

# Helpers from server.py scope
ROOT_DIR = __import__("pathlib").Path(os.path.dirname(os.path.abspath(__file__)))

async def get_current_user(request: Request):
    """Extract user from JWT token in request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

async def require_admin(request: Request):
    """Verify admin role from JWT."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "founder", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_jwt_token(user_data: dict, expires_hours: int = 24):
    """Generate JWT token."""
    import time as _time
    payload = {
        **user_data,
        "exp": int(_time.time()) + (expires_hours * 3600),
        "iat": int(_time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============= PAYMENT ROUTES =============


@router.post("/payments/stripe/checkout")
async def create_stripe_checkout(checkout_data: CheckoutRequest, request: Request):
    order = await db.orders.find_one({"id": checkout_data.order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_modules = get_stripe_checkout()
    StripeCheckout = stripe_modules['StripeCheckout']
    CheckoutSessionRequest = stripe_modules['CheckoutSessionRequest']
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    success_url = f"{checkout_data.origin_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{checkout_data.origin_url}/checkout/cancel"

    checkout_request = CheckoutSessionRequest(
        amount=float(order["total"]),
        currency="cad",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": order["id"], "order_number": order["order_number"]},
    )

    CheckoutSessionResponse = stripe_modules.get('CheckoutSessionResponse')
    session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(
        checkout_request
    )

    # Update order with stripe session ID
    await db.orders.update_one(
        {"id": checkout_data.order_id},
        {"$set": {"stripe_session_id": session.session_id}},
    )

    # Create payment transaction record
    transaction = PaymentTransaction(
        order_id=order["id"],
        session_id=session.session_id,
        amount=float(order["total"]),
        currency="cad",
        payment_method="stripe",
        payment_status="pending",
        metadata={"order_number": order["order_number"]},
    )
    trans_dict = transaction.model_dump()
    trans_dict["created_at"] = trans_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(trans_dict)

    return {"url": session.url, "session_id": session.session_id}


# Coinbase Commerce API key (from environment)
COINBASE_COMMERCE_API_KEY = os.environ.get("COINBASE_COMMERCE_API_KEY", "")


class CoinbaseCheckoutRequest(BaseModel):
    order_id: str
    origin_url: str


@router.post("/payments/coinbase/checkout")
async def create_coinbase_checkout(
    checkout_data: CoinbaseCheckoutRequest, request: Request
):
    """Create a Coinbase Commerce checkout for crypto payments"""
    order = await db.orders.find_one({"id": checkout_data.order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not COINBASE_COMMERCE_API_KEY:
        raise HTTPException(status_code=500, detail="Coinbase Commerce not configured")

    try:
        import httpx

        # Create a charge via Coinbase Commerce API
        charge_data = {
            "name": f"ReRoots Order #{order.get('order_number', order['id'][:8])}",
            "description": f"ReRoots Skincare Order - {len(order.get('items', []))} item(s)",
            "pricing_type": "fixed_price",
            "local_price": {"amount": str(order["total"]), "currency": "CAD"},
            "metadata": {
                "order_id": order["id"],
                "order_number": order.get("order_number", ""),
            },
            "redirect_url": f"{checkout_data.origin_url}/checkout/success?coinbase=true&order_id={order['id']}",
            "cancel_url": f"{checkout_data.origin_url}/checkout/cancel",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.commerce.coinbase.com/charges",
                json=charge_data,
                headers={
                    "X-CC-Api-Key": COINBASE_COMMERCE_API_KEY,
                    "X-CC-Version": "2018-03-22",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 201:
                logging.error(f"Coinbase API error: {response.text}")
                raise HTTPException(
                    status_code=500, detail="Failed to create crypto checkout"
                )

            charge = response.json()["data"]

        # Update order with Coinbase charge ID
        await db.orders.update_one(
            {"id": checkout_data.order_id},
            {"$set": {"coinbase_charge_id": charge["id"], "payment_method": "crypto"}},
        )

        # Create payment transaction record
        transaction = {
            "order_id": order["id"],
            "session_id": charge["id"],
            "amount": float(order["total"]),
            "currency": "CAD",
            "payment_method": "coinbase",
            "payment_status": "pending",
            "metadata": {
                "order_number": order.get("order_number", ""),
                "hosted_url": charge["hosted_url"],
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(transaction)

        return {"success": True, "url": charge["hosted_url"], "charge_id": charge["id"]}

    except httpx.HTTPError as e:
        logging.error(f"Coinbase Commerce request failed: {e}")
        raise HTTPException(
            status_code=500, detail="Crypto payment service unavailable"
        )


# ============= TD/BAMBORA PAYMENT INTEGRATION =============
class BamboraPaymentRequest(BaseModel):
    order_id: str
    card_number: str
    expiry_month: int = Field(..., ge=1, le=12)
    expiry_year: int
    cvv: str = Field(..., min_length=3, max_length=4)
    cardholder_name: str
    billing_address: Optional[str] = None
    billing_postal_code: Optional[str] = None


@router.post("/payments/bambora/checkout")
async def create_bambora_checkout(
    payment_data: BamboraPaymentRequest, request: Request
):
    """Process payment through TD/Bambora payment gateway"""
    import httpx

    # Enhanced logging for debugging payment issues
    logging.info("=== BAMBORA CHECKOUT REQUEST ===")
    logging.info(f"Order ID: {payment_data.order_id}")
    logging.info(f"Cardholder: {payment_data.cardholder_name}")
    logging.info(f"Card last 4: {payment_data.card_number[-4:] if len(payment_data.card_number) >= 4 else 'N/A'}")
    logging.info(f"Expiry: {payment_data.expiry_month}/{payment_data.expiry_year}")
    logging.info(f"Merchant ID configured: {bool(BAMBORA_MERCHANT_ID)}")
    logging.info(f"API Passcode configured: {bool(BAMBORA_API_PASSCODE)}")

    if not BAMBORA_MERCHANT_ID or not BAMBORA_API_PASSCODE:
        logging.error("Bambora credentials missing!")
        raise HTTPException(
            status_code=500, detail="TD Merchant payment not configured"
        )

    # Find the order
    order = await db.orders.find_one({"id": payment_data.order_id}, {"_id": 0})
    if not order:
        logging.error(f"Order not found: {payment_data.order_id}")
        raise HTTPException(status_code=404, detail="Order not found")
    
    logging.info(f"Order found: Total=${order.get('total')}, Status={order.get('payment_status')}")

    try:
        # Prepare Bambora API authentication
        credentials = f"{BAMBORA_MERCHANT_ID}:{BAMBORA_API_PASSCODE}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Passcode {encoded_credentials}",
            "Content-Type": "application/json",
        }

        # Convert amount to cents (Bambora expects amount in cents)
        amount_cents = int(float(order["total"]) * 100)
        logging.info(f"Amount in cents: {amount_cents}")

        # Prepare payment payload with 3D Secure and AVS
        payload = {
            "payment_method": "card",
            "order_number": order.get("order_number", order["id"][:8]),
            "amount": amount_cents / 100,  # Bambora API expects decimal amount
            "card": {
                "name": payment_data.cardholder_name,
                "number": payment_data.card_number.replace(" ", "").replace("-", ""),
                "expiry_month": str(payment_data.expiry_month).zfill(2),
                "expiry_year": str(payment_data.expiry_year)[-2:],
                "cvd": payment_data.cvv,
                "complete": True,  # Capture payment immediately
            },
            # Enable 3D Secure authentication
            "3d_secure": {
                "enabled": True,
                "browser": {
                    "accept_header": "text/html",
                    "java_enabled": False,
                    "language": "en-CA",
                    "color_depth": "24",
                    "screen_height": 800,
                    "screen_width": 1920,
                    "time_zone": -300,
                    "user_agent": "Mozilla/5.0",
                    "javascript_enabled": True,
                },
            },
            # Require CVV match
            "term_url": f"{os.environ.get('FRONTEND_URL')}/checkout/3ds-callback",
        }

        # Add billing address for AVS (Address Verification Service)
        shipping = order.get("shipping_address", {})
        payload["billing"] = {
            "name": payment_data.cardholder_name,
            "address_line1": payment_data.billing_address
            or shipping.get("address", ""),
            "city": shipping.get("city", ""),
            "province": shipping.get("state", "ON"),
            "postal_code": payment_data.billing_postal_code
            or shipping.get("postal_code", ""),
            "country": "CA",
            "email_address": shipping.get("email", ""),
            "phone_number": shipping.get("phone", ""),
        }

        # Log the full payload (without sensitive card data)
        safe_payload = {**payload}
        safe_payload['card'] = {**payload['card'], 'number': 'XXXX' + payload['card']['number'][-4:], 'cvd': 'XXX'}
        logging.info(f"Bambora API payload: {safe_payload}")
        logging.info(f"Bambora API URL: {BAMBORA_API_URL}/payments")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BAMBORA_API_URL}/payments",
                json=payload,
                headers=headers,
                timeout=30.0,
            )

            response_data = response.json()
            logging.info("=== BAMBORA RESPONSE ===")
            logging.info(f"Status Code: {response.status_code}")
            logging.info(f"Response Data: {response_data}")

            # Check for 3D Secure redirect requirement
            if response_data.get("3d_secure", {}).get("status") == "challenge":
                logging.info("3D Secure challenge required")
                # Customer needs to complete 3D Secure authentication
                return {
                    "success": False,
                    "requires_3ds": True,
                    "redirect_url": response_data.get("3d_secure", {}).get("acs_url"),
                    "pareq": response_data.get("3d_secure", {}).get("pareq"),
                    "transaction_id": response_data.get("id"),
                    "message": "Please complete 3D Secure verification",
                }

            if (
                response.status_code in [200, 201]
                and response_data.get("approved") == 1
            ):
                logging.info("Payment APPROVED!")
                # Check AVS (Address Verification) result
                avs_result = response_data.get("card", {}).get("avs_result", "")
                cvd_result = response_data.get("card", {}).get("cvd_result", "")

                # AVS codes: M=Match, N=No Match, U=Unavailable
                # CVD codes: 1=Match, 2=No Match, 3=Not Processed
                avs_failed = avs_result in ["N", "A", "Z"]  # Postal or address mismatch
                cvd_failed = cvd_result == "2"  # CVV mismatch

                if cvd_failed:
                    logging.warning(f"CVV mismatch for order {payment_data.order_id}")
                    # Void the transaction for security
                    try:
                        await client.post(
                            f"{BAMBORA_API_URL}/payments/{response_data.get('id')}/void",
                            headers=headers,
                            json={"amount": amount_cents / 100},
                        )
                    except:
                        pass
                    return {
                        "success": False,
                        "message": "Card security code (CVV) does not match. Please check and try again.",
                        "order_id": order["id"],
                    }

                # Payment approved
                bambora_transaction_id = response_data.get("id", "")

                # Update order status
                await db.orders.update_one(
                    {"id": payment_data.order_id},
                    {
                        "$set": {
                            "payment_status": "paid",
                            "order_status": "processing",
                            "payment_method": "bambora_td",
                            "bambora_transaction_id": bambora_transaction_id,
                            "paid_at": datetime.utcnow().isoformat(),
                            "avs_result": avs_result,
                            "cvd_result": cvd_result,
                            "3ds_status": response_data.get("3d_secure", {}).get(
                                "status", "not_enrolled"
                            ),
                        }
                    },
                )

                # Create payment transaction record
                transaction = {
                    "id": str(uuid.uuid4()),
                    "order_id": order["id"],
                    "transaction_id": bambora_transaction_id,
                    "amount": float(order["total"]),
                    "currency": "CAD",
                    "payment_method": "bambora_td",
                    "payment_status": "paid",
                    "card_type": response_data.get("card", {}).get("card_type", ""),
                    "last_four": payment_data.card_number[-4:],
                    "auth_code": response_data.get("auth_code", ""),
                    "avs_result": avs_result,
                    "cvd_result": cvd_result,
                    "created_at": datetime.utcnow().isoformat(),
                }
                await db.payment_transactions.insert_one(transaction)

                # DEDUCT INVENTORY: Reduce stock for all items in the order
                try:
                    await deduct_inventory_for_order(order["id"])
                    logging.info(f"[Bambora] Inventory deducted for order {order['id']}")
                except Exception as inv_error:
                    logging.error(f"[Bambora] Failed to deduct inventory: {inv_error}")

                # Send confirmation email
                customer_email = order.get("shipping_address", {}).get("email")
                if customer_email:
                    try:
                        await send_order_confirmation_email(order, customer_email)
                    except Exception as email_error:
                        logging.error(
                            f"Failed to send confirmation email: {email_error}"
                        )

                # Track gift conversion (if user claimed a gift recently)
                try:
                    user_id = order.get("user_id")
                    if user_id:
                        await check_and_link_gift_to_order(user_id, order["id"], order.get("total", 0))
                except Exception as gift_error:
                    logging.error(f"[Gift] Failed to track conversion: {gift_error}")

                # AUTO-SHIP: Create shipping label automatically
                try:
                    asyncio.create_task(process_auto_shipping(order["id"]))
                    logging.info(f"[Bambora] Auto-shipping task queued for order {order['id']}")
                except Exception as ship_error:
                    logging.error(f"[Bambora] Failed to queue auto-shipping: {ship_error}")

                return {
                    "success": True,
                    "message": "Payment processed successfully",
                    "transaction_id": bambora_transaction_id,
                    "order_id": order["id"],
                    "auth_code": response_data.get("auth_code", ""),
                }
            else:
                # Payment declined - provide user-friendly error messages
                raw_message = response_data.get("message", "Payment declined")
                response_code = response_data.get("response_code", "")
                logging.warning(f"Bambora payment declined: {raw_message} (code: {response_code})")
                
                # Map Bambora error codes to user-friendly messages
                friendly_messages = {
                    "CALL HELP DESK": "Your bank has flagged this transaction for verification. Please call the number on the back of your card to authorize online purchases, then try again.",
                    "DECLINED": "Your card was declined. Please check your card details or try a different payment method.",
                    "INVALID CARD": "The card number appears to be invalid. Please check and re-enter your card details.",
                    "EXPIRED CARD": "Your card has expired. Please use a different card.",
                    "INSUFFICIENT FUNDS": "Your card has insufficient funds. Please try a different payment method.",
                    "CVV MISMATCH": "The security code (CVV) doesn't match. Please check the 3-digit code on the back of your card.",
                    "DO NOT HONOUR": "Your bank has declined this transaction. Please contact your bank or try a different card.",
                    "PICK UP CARD": "Your bank has requested this card be declined. Please contact your bank or use a different card.",
                    "LOST CARD": "This card has been reported as lost. Please use a different card.",
                    "STOLEN CARD": "This card has been flagged. Please contact your bank.",
                }
                
                # Check for matching error message
                error_upper = raw_message.upper().strip()
                user_message = friendly_messages.get(error_upper)
                
                if not user_message:
                    # Check for partial matches
                    for key, msg in friendly_messages.items():
                        if key in error_upper:
                            user_message = msg
                            break
                
                # Default message if no match found
                if not user_message:
                    user_message = f"Payment was declined by your bank. Please contact your card issuer or try a different payment method. (Ref: {raw_message})"

                return {
                    "success": False,
                    "message": user_message,
                    "raw_error": raw_message,
                    "response_code": response_code,
                    "order_id": order["id"],
                    "help_text": "If this issue persists, please contact your bank to authorize online transactions.",
                }

    except httpx.TimeoutException:
        logging.error("Bambora API timeout")
        raise HTTPException(
            status_code=504, detail="Payment gateway timeout - please try again"
        )
    except httpx.HTTPError as e:
        logging.error(f"Bambora HTTP error: {e}")
        raise HTTPException(
            status_code=500, detail="Payment gateway communication error"
        )
    except Exception as e:
        logging.error(f"Bambora payment error: {e}")
        raise HTTPException(status_code=500, detail="Payment processing failed")


@router.get("/payments/bambora/status/{transaction_id}")
async def get_bambora_payment_status(transaction_id: str):
    """Get status of a Bambora payment transaction"""
    import httpx

    if not BAMBORA_MERCHANT_ID or not BAMBORA_API_PASSCODE:
        raise HTTPException(
            status_code=500, detail="TD Merchant payment not configured"
        )

    try:
        credentials = f"{BAMBORA_MERCHANT_ID}:{BAMBORA_API_PASSCODE}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Passcode {encoded_credentials}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BAMBORA_API_URL}/payments/{transaction_id}",
                headers=headers,
                timeout=30.0,
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")

    except httpx.HTTPError as e:
        logging.error(f"Bambora status check error: {e}")
        raise HTTPException(status_code=500, detail="Failed to check payment status")


@router.get("/payments/stripe/status/{session_id}")
async def get_stripe_payment_status(session_id: str, request: Request):
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_modules = get_stripe_checkout()
    StripeCheckout = stripe_modules['StripeCheckout']
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    status = await stripe_checkout.get_checkout_status(
        session_id
    )

    # Update order and transaction status
    if status.payment_status == "paid":
        # Check if already processed to avoid duplicate emails
        existing_order = await db.orders.find_one(
            {"stripe_session_id": session_id}, {"_id": 0}
        )
        was_already_paid = (
            existing_order and existing_order.get("payment_status") == "paid"
        )

        await db.orders.update_one(
            {"stripe_session_id": session_id},
            {"$set": {"payment_status": "paid", "order_status": "processing"}},
        )
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"payment_status": "paid"}}
        )

        # Send order confirmation email (only if not already sent)
        order = await db.orders.find_one({"stripe_session_id": session_id}, {"_id": 0})
        if order and not was_already_paid and not order.get("receipt_sent"):
            # Get customer email from shipping address or user
            customer_email = order.get("shipping_address", {}).get("email")
            if not customer_email and order.get("user_id"):
                user = await db.users.find_one({"id": order["user_id"]}, {"_id": 0})
                customer_email = user.get("email") if user else None

            if customer_email:
                await send_order_confirmation_email(order, customer_email)

            # Award loyalty points (250 per product)
            if not order.get("points_awarded"):
                try:
                    total_quantity = sum(
                        item.get("quantity", 1) for item in order.get("items", [])
                    )
                    points_earned = total_quantity * POINTS_PER_PRODUCT

                    user_id = order.get("user_id")
                    if user_id:
                        # Award points to logged-in user
                        history_entry = {
                            "id": str(uuid.uuid4()),
                            "type": "earned",
                            "points": points_earned,
                            "description": f"Purchase - Order #{order.get('order_number', order['id'][:8])}",
                            "order_id": order["id"],
                            "date": datetime.now(timezone.utc).isoformat(),
                        }

                        await db.loyalty_points.update_one(
                            {"user_id": user_id},
                            {
                                "$inc": {
                                    "balance": points_earned,
                                    "lifetime_earned": points_earned,
                                },
                                "$push": {"history": history_entry},
                                "$setOnInsert": {
                                    "id": str(uuid.uuid4()),
                                    "user_id": user_id,
                                    "created_at": datetime.now(
                                        timezone.utc
                                    ).isoformat(),
                                },
                            },
                            upsert=True,
                        )
                        logger.info(
                            f"Awarded {points_earned} points to user {user_id} for Stripe order {order['id']}"
                        )
                    else:
                        # Store as pending for guest checkout
                        await db.pending_points.insert_one(
                            {
                                "id": str(uuid.uuid4()),
                                "email": (
                                    customer_email.lower() if customer_email else ""
                                ),
                                "order_id": order["id"],
                                "points": points_earned,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        logger.info(
                            f"Stored {points_earned} pending points for guest {customer_email}"
                        )

                    # Mark order as points awarded
                    await db.orders.update_one(
                        {"id": order["id"]}, {"$set": {"points_awarded": points_earned}}
                    )
                except Exception as e:
                    logger.error(f"Error awarding points: {e}")

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
    }


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    stripe_signature = request.headers.get("Stripe-Signature")

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"

    stripe_modules = get_stripe_checkout()
    StripeCheckout = stripe_modules['StripeCheckout']
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    try:
        webhook_response = await stripe_checkout.handle_webhook(body, stripe_signature)

        if webhook_response.payment_status == "paid":
            # Check if already processed to avoid duplicate emails
            existing_order = await db.orders.find_one(
                {"stripe_session_id": webhook_response.session_id}, {"_id": 0}
            )
            was_already_paid = (
                existing_order and existing_order.get("payment_status") == "paid"
            )

            await db.orders.update_one(
                {"stripe_session_id": webhook_response.session_id},
                {"$set": {"payment_status": "paid", "order_status": "processing"}},
            )
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {"payment_status": "paid"}},
            )

            # Send order confirmation email (only if not already sent)
            order = await db.orders.find_one(
                {"stripe_session_id": webhook_response.session_id}, {"_id": 0}
            )
            if order and not was_already_paid and not order.get("receipt_sent"):
                customer_email = order.get("shipping_address", {}).get("email")
                if not customer_email and order.get("user_id"):
                    user = await db.users.find_one({"id": order["user_id"]}, {"_id": 0})
                    customer_email = user.get("email") if user else None

                if customer_email:
                    await send_order_confirmation_email(order, customer_email)
            
            # AWARD LOYALTY POINTS for this purchase
            if order and not was_already_paid and order.get("user_id") and not order.get("points_awarded"):
                try:
                    user_id = order.get("user_id")
                    items = order.get("items", [])
                    total_quantity = sum(item.get("quantity", 1) for item in items)
                    config = await get_loyalty_config()
                    points_to_award = total_quantity * config.get("points_per_product", 200)
                    
                    # Update or create loyalty points record
                    await db.loyalty_points.update_one(
                        {"user_id": user_id},
                        {
                            "$inc": {"balance": points_to_award, "lifetime_earned": points_to_award},
                            "$setOnInsert": {
                                "id": str(uuid.uuid4()),
                                "user_id": user_id,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            },
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                        },
                        upsert=True
                    )
                    
                    # Mark order as having points awarded
                    await db.orders.update_one(
                        {"stripe_session_id": webhook_response.session_id},
                        {"$set": {"points_awarded": points_to_award}}
                    )
                    
                    logging.info(f"[Stripe] Awarded {points_to_award} loyalty points to user {user_id}")
                except Exception as points_error:
                    logging.error(f"[Stripe] Failed to award loyalty points: {points_error}")

        return {"status": "success"}
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return {"status": "error"}


# ============= AD BUDGET / CREDITS SYSTEM =============


@router.get("/admin/ad-budget")
async def get_ad_budget(current_user: dict = Depends(require_admin)):
    """Get current ad budget/credits balance"""
    budget = await db.ad_budget.find_one({"store_id": "main"}, {"_id": 0})
    if not budget:
        # Initialize with 0 balance
        budget = {
            "store_id": "main",
            "balance": 0.0,
            "currency": "CAD",
            "total_deposited": 0.0,
            "total_spent": 0.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.ad_budget.insert_one(budget)
        budget.pop("_id", None)
    return budget


@router.get("/admin/ad-budget/transactions")
async def get_ad_budget_transactions(current_user: dict = Depends(require_admin)):
    """Get ad budget transaction history"""
    transactions = (
        await db.ad_budget_transactions.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return transactions


@router.post("/admin/ad-budget/add-funds")
async def create_ad_budget_checkout(request: Request, amount: float = 50.0):
    """Create Stripe checkout session to add ad budget funds"""
    user = await require_admin(request)

    if amount < 10:
        raise HTTPException(status_code=400, detail="Minimum amount is $10")
    if amount > 10000:
        raise HTTPException(status_code=400, detail="Maximum amount is $10,000")

    # Check if Stripe is properly configured
    if (
        not STRIPE_API_KEY
        or STRIPE_API_KEY == "sk_test_emergent"
        or len(STRIPE_API_KEY) < 20
    ):
        # Demo mode - add funds directly without payment
        transaction_id = str(uuid.uuid4())

        # Create completed transaction
        transaction = {
            "id": transaction_id,
            "type": "deposit",
            "amount": amount,
            "currency": "CAD",
            "status": "completed",
            "stripe_session_id": "demo_" + transaction_id,
            "user_id": user["id"],
            "user_email": user.get("email", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "demo_mode": True,
        }
        await db.ad_budget_transactions.insert_one(transaction)

        # Update ad budget balance
        await db.ad_budget.update_one(
            {"store_id": "main"},
            {
                "$inc": {"balance": amount, "total_deposited": amount},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            },
            upsert=True,
        )

        logging.info(f"Demo mode: Ad budget increased by ${amount}")
        return {
            "demo_mode": True,
            "message": f"Demo mode: ${amount} added to ad budget",
            "transaction_id": transaction_id,
            "new_balance": amount,
        }

    # Real Stripe checkout
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/ad-budget"
    origin = request.headers.get("origin", host_url)

    stripe_modules = get_stripe_checkout()
    StripeCheckout = stripe_modules['StripeCheckout']
    CheckoutSessionRequest = stripe_modules['CheckoutSessionRequest']
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    transaction_id = str(uuid.uuid4())
    success_url = f"{origin}/reroots-admin?tab=ads&payment=success&transaction_id={transaction_id}"
    cancel_url = f"{origin}/reroots-admin?tab=ads&payment=cancelled"

    checkout_request = CheckoutSessionRequest(
        amount=amount,
        currency="cad",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "ad_budget",
            "transaction_id": transaction_id,
            "user_id": user["id"],
        },
    )

    session = await stripe_checkout.create_checkout_session(checkout_request)

    # Create pending transaction
    transaction = {
        "id": transaction_id,
        "type": "deposit",
        "amount": amount,
        "currency": "CAD",
        "status": "pending",
        "stripe_session_id": session.session_id,
        "user_id": user["id"],
        "user_email": user.get("email", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ad_budget_transactions.insert_one(transaction)

    return {
        "checkout_url": session.url,
        "session_id": session.session_id,
        "transaction_id": transaction_id,
    }


@router.post("/webhook/ad-budget")
async def ad_budget_webhook(request: Request):
    """Handle Stripe webhook for ad budget payments"""
    try:
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/ad-budget"
        
        stripe_modules = get_stripe_checkout()
        StripeCheckout = stripe_modules['StripeCheckout']
        
        stripe_checkout = StripeCheckout(
            api_key=STRIPE_API_KEY, webhook_url=webhook_url
        )

        body = await request.body()
        event = stripe_checkout.verify_webhook(body.decode())

        if event.event_type == "checkout.session.completed":
            session_data = event.data
            metadata = session_data.get("metadata", {})

            if metadata.get("type") == "ad_budget":
                transaction_id = metadata.get("transaction_id")
                amount = (
                    float(session_data.get("amount_total", 0)) / 100
                )  # Convert from cents

                # Update transaction status
                await db.ad_budget_transactions.update_one(
                    {"id": transaction_id},
                    {
                        "$set": {
                            "status": "completed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
                    },
                )

                # Update ad budget balance
                await db.ad_budget.update_one(
                    {"store_id": "main"},
                    {
                        "$inc": {"balance": amount, "total_deposited": amount},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                    },
                    upsert=True,
                )

                logging.info(f"Ad budget increased by ${amount}")

        return {"status": "success"}
    except Exception as e:
        logging.error(f"Ad budget webhook error: {e}")
        return {"status": "error"}


@router.post("/admin/ad-budget/allocate")
async def allocate_ad_budget(
    campaign_id: str, amount: float, current_user: dict = Depends(require_admin)
):
    """Allocate budget to a specific ad campaign"""
    # Check available balance
    budget = await db.ad_budget.find_one({"store_id": "main"}, {"_id": 0})
    if not budget or budget.get("balance", 0) < amount:
        raise HTTPException(status_code=400, detail="Insufficient ad budget balance")

    # Update campaign budget
    await db.ad_campaigns.update_one(
        {"id": campaign_id}, {"$inc": {"allocated_budget": amount}}
    )

    # Deduct from balance
    await db.ad_budget.update_one(
        {"store_id": "main"},
        {
            "$inc": {"balance": -amount, "total_spent": amount},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )

    # Record transaction
    transaction = {
        "id": str(uuid.uuid4()),
        "type": "allocation",
        "amount": -amount,
        "currency": "CAD",
        "status": "completed",
        "campaign_id": campaign_id,
        "user_id": current_user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ad_budget_transactions.insert_one(transaction)

    return {
        "message": f"${amount} allocated to campaign",
        "new_balance": budget["balance"] - amount,
    }


# ============= PAYPAL REST API INTEGRATION (v2 Orders API) =============


class PayPalOrderRequest(BaseModel):
    order_id: str  # Internal order ID


@router.post("/payments/paypal/create-order")
async def create_paypal_order(data: PayPalOrderRequest, request: Request):
    """Create a PayPal order for payment processing using REST API v2"""
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise HTTPException(status_code=500, detail="PayPal is not configured")
    
    # Get the order from database
    order = await db.orders.find_one({"id": data.order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    try:
        # Get OAuth token
        access_token = await get_paypal_access_token()
        
        # Create PayPal order via REST API
        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": data.order_id,
                "description": f"ReRoots Order #{order.get('order_number', data.order_id[:8])}",
                "custom_id": data.order_id,
                "amount": {
                    "currency_code": "CAD",
                    "value": str(round(float(order["total"]), 2))
                }
            }],
            "application_context": {
                "brand_name": "ReRoots",
                "landing_page": "LOGIN",
                "user_action": "PAY_NOW",
                "return_url": f"{os.environ.get('FRONTEND_URL')}/checkout/success?order_id={data.order_id}&payment_method=paypal_api",
                "cancel_url": f"{os.environ.get('FRONTEND_URL')}/checkout?cancelled=true"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_API_BASE}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=order_payload
            )
            
            if response.status_code not in [200, 201]:
                logging.error(f"PayPal create order error: {response.text}")
                raise HTTPException(status_code=500, detail=f"PayPal error: {response.text}")
            
            paypal_order = response.json()
        
        logging.info(f"PayPal order created: {paypal_order.get('id')}")
        
        # Store PayPal order ID in our order
        await db.orders.update_one(
            {"id": data.order_id},
            {"$set": {"paypal_order_id": paypal_order.get("id")}}
        )
        
        # Extract approval URL for redirect flow
        links = paypal_order.get("links", [])
        approval_url = next((link["href"] for link in links if link.get("rel") == "approve"), None)
        
        return {
            "success": True,
            "id": paypal_order.get("id"),
            "order_id": data.order_id,
            "status": paypal_order.get("status", "CREATED"),
            "links": links,
            "approval_url": approval_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PayPal create order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payments/paypal/return")
async def paypal_return_handler(token: str = None, PayerID: str = None):
    """Handle PayPal redirect after user approval"""
    # This endpoint handles the return from PayPal redirect flow
    # The frontend will handle the actual capture
    return {
        "success": True,
        "paypal_order_id": token,
        "payer_id": PayerID,
        "message": "PayPal payment approved. Processing..."
    }


@router.post("/payments/paypal/capture")
async def capture_paypal_payment(request: Request):
    """Capture a PayPal payment after user approval using REST API v2"""
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise HTTPException(status_code=500, detail="PayPal is not configured")
    
    data = await request.json()
    paypal_order_id = data.get("orderID")  # PayPal order ID
    internal_order_id = data.get("order_id")  # Our internal order ID
    
    if not paypal_order_id:
        raise HTTPException(status_code=400, detail="Missing PayPal orderID")
    
    try:
        # Get OAuth token
        access_token = await get_paypal_access_token()
        
        # Capture the PayPal order via REST API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_API_BASE}/v2/checkout/orders/{paypal_order_id}/capture",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code not in [200, 201]:
                logging.error(f"PayPal capture error: {response.text}")
                raise HTTPException(status_code=500, detail=f"PayPal capture failed: {response.text}")
            
            captured_order = response.json()
        
        logging.info(f"PayPal order captured: {paypal_order_id}, status: {captured_order.get('status')}")
        
        # Update order status in our database
        if internal_order_id:
            order = await db.orders.find_one({"id": internal_order_id}, {"_id": 0})
            
            # Extract payer info from response
            payer = captured_order.get("payer", {})
            payer_email = payer.get("email_address")
            payer_id = payer.get("payer_id")
            
            await db.orders.update_one(
                {"id": internal_order_id},
                {
                    "$set": {
                        "payment_status": "paid",
                        "order_status": "processing",
                        "payment_method": "paypal_api",
                        "paypal_order_id": paypal_order_id,
                        "paypal_payer_id": payer_id,
                        "paypal_payer_email": payer_email,
                        "paid_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            # Create payment transaction record
            transaction = {
                "id": str(uuid.uuid4()),
                "order_id": internal_order_id,
                "transaction_id": paypal_order_id,
                "amount": float(order["total"]) if order else 0,
                "currency": "CAD",
                "payment_method": "paypal_api",
                "payment_status": "paid",
                "payer_id": payer_id,
                "payer_email": payer_email,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.payment_transactions.insert_one(transaction)
            
            # DEDUCT INVENTORY
            try:
                await deduct_inventory_for_order(internal_order_id)
                logging.info(f"[PayPal] Inventory deducted for order {internal_order_id}")
            except Exception as inv_error:
                logging.error(f"[PayPal] Failed to deduct inventory: {inv_error}")
            
            # Send confirmation email
            if order:
                customer_email = order.get("shipping_address", {}).get("email")
                if customer_email:
                    try:
                        await send_order_confirmation_email(order, customer_email)
                    except Exception as email_error:
                        logging.error(f"Failed to send confirmation email: {email_error}")
            
            # Track gift conversion
            if order:
                try:
                    user_id = order.get("user_id")
                    if user_id:
                        await check_and_link_gift_to_order(user_id, internal_order_id, order.get("total", 0))
                except Exception as gift_error:
                    logging.error(f"[Gift] Failed to track conversion: {gift_error}")
            
            # AWARD LOYALTY POINTS for this purchase
            if order:
                try:
                    user_id = order.get("user_id")
                    customer_email = order.get("customer_email", "").lower() or order.get("shipping_address", {}).get("email", "").lower()
                    
                    # Try to find user by email if no user_id
                    if not user_id and customer_email:
                        user = await db.users.find_one({"email": customer_email}, {"_id": 0})
                        if user:
                            user_id = user.get("id")
                    
                    if user_id:
                        items = order.get("items", [])
                        total_quantity = sum(item.get("quantity", 1) for item in items)
                        config = await get_loyalty_config()
                        points_to_award = total_quantity * config.get("points_per_product", 200)
                        
                        # Check if points already awarded for this order
                        if not order.get("points_awarded"):
                            # Update or create loyalty points record
                            await db.loyalty_points.update_one(
                                {"user_id": user_id},
                                {
                                    "$inc": {"balance": points_to_award, "lifetime_earned": points_to_award},
                                    "$setOnInsert": {
                                        "id": str(uuid.uuid4()),
                                        "user_id": user_id,
                                        "created_at": datetime.now(timezone.utc).isoformat()
                                    },
                                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                                },
                                upsert=True
                            )
                            
                            # Mark order as having points awarded
                            await db.orders.update_one(
                                {"id": internal_order_id},
                                {"$set": {"points_awarded": points_to_award}}
                            )
                            
                            logging.info(f"[PayPal] Awarded {points_to_award} loyalty points to user {user_id}")
                    elif customer_email:
                        # Guest checkout - store points as pending
                        items = order.get("items", [])
                        total_quantity = sum(item.get("quantity", 1) for item in items)
                        config = await get_loyalty_config()
                        points_to_award = total_quantity * config.get("points_per_product", 200)
                        
                        if not order.get("points_awarded"):
                            await db.pending_points.update_one(
                                {"email": customer_email, "order_id": internal_order_id},
                                {
                                    "$setOnInsert": {
                                        "id": str(uuid.uuid4()),
                                        "email": customer_email,
                                        "order_id": internal_order_id,
                                        "points": points_to_award,
                                        "created_at": datetime.now(timezone.utc).isoformat()
                                    }
                                },
                                upsert=True
                            )
                            
                            await db.orders.update_one(
                                {"id": internal_order_id},
                                {"$set": {"points_awarded": points_to_award, "points_pending": True}}
                            )
                            
                            logging.info(f"[PayPal] Stored {points_to_award} pending points for guest {customer_email}")
                except Exception as points_error:
                    logging.error(f"[PayPal] Failed to award loyalty points: {points_error}")
            
            # Broadcast to admin
            await broadcast_admin_event("new_order", {
                "order_id": internal_order_id,
                "order_number": order.get("order_number") if order else "",
                "total": order["total"] if order else 0,
                "customer_email": order.get("shipping_address", {}).get("email") if order else "",
                "payment_method": "PayPal"
            })
            
            # AUTO-SHIP
            try:
                asyncio.create_task(process_auto_shipping(internal_order_id))
                logging.info(f"[PayPal] Auto-shipping task queued for order {internal_order_id}")
            except Exception as ship_error:
                logging.error(f"[PayPal] Failed to queue auto-shipping: {ship_error}")
        
        return {
            "success": True,
            "paypal_order_id": paypal_order_id,
            "status": captured_order.get("status", "COMPLETED"),
            "order_id": internal_order_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"PayPal capture error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payments/paypal/config")
async def get_paypal_config():
    """Get PayPal client ID for frontend initialization"""
    return {
        "client_id": PAYPAL_CLIENT_ID,
        "mode": PAYPAL_MODE
    }


@router.post("/payments/paypal/client-token")
async def generate_paypal_client_token(request: Request = None):
    """
    Generate a browser-safe client token for PayPal JavaScript SDK v6.
    Uses the correct method: response_type=client_token in OAuth2 token request.
    """
    import httpx
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise HTTPException(status_code=500, detail="PayPal credentials not configured")
    
    # Determine the API URL based on mode
    api_base = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"
    
    # Create Basic auth header
    credentials = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}".encode()).decode()
    
    # Get the domain for the client token (needed for SDK v6)
    # PayPal requires the domain to match where the SDK is loaded
    domain = "reroots.ca"  # Default to production domain
    
    if request:
        # Try multiple headers to determine the actual domain
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        
        # Priority: Origin > Referer > Host
        source_url = origin or referer or ""
        if source_url:
            # Extract domain from URL (e.g., https://reroots.ca/checkout -> reroots.ca)
            domain = source_url.replace("https://", "").replace("http://", "").split("/")[0]
        elif host:
            domain = host.split(":")[0]  # Remove port if present
        
        # Log for debugging
        logging.info(f"PayPal client token request - Origin: {origin}, Referer: {referer}, Host: {host}, Using domain: {domain}")
    
    try:
        async with httpx.AsyncClient() as client:
            # Request client token directly using response_type=client_token
            # This is the correct method for SDK v6
            auth_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {credentials}"
            }
            
            # Include domain and response_type for client token
            token_data = {
                "grant_type": "client_credentials",
                "response_type": "client_token",
                "intent": "sdk_init",
                "domains[]": domain
            }
            
            auth_response = await client.post(
                f"{api_base}/v1/oauth2/token",
                data=token_data,
                headers=auth_headers,
                timeout=30.0
            )
            auth_response.raise_for_status()
            response_data = auth_response.json()
            
            # For SDK v6 with response_type=client_token, the access_token IS the client token
            client_token = response_data.get("access_token")
            expires_in = response_data.get("expires_in", 3600)
            
            if not client_token:
                logging.error(f"No client_token in response: {response_data}")
                raise HTTPException(status_code=500, detail="Failed to generate PayPal client token")
            
            logging.info(f"PayPal client token generated successfully for domain: {domain}")
            
            return {
                "clientToken": client_token,
                "expiresIn": expires_in
            }
            
    except httpx.HTTPStatusError as e:
        logging.error(f"PayPal client token HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail=f"PayPal API error: {e.response.text}")
    except Exception as e:
        logging.error(f"PayPal client token error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PayPal client token: {str(e)}")


@router.post("/payments/paypal/webhooks")
async def handle_paypal_webhook(request: Request):
    """
    PayPal Webhook handler - Safety net for payment confirmations.
    Handles CHECKOUT.ORDER.COMPLETED and PAYMENT.CAPTURE.COMPLETED events.
    This ensures we process payments even if the user closes their browser.
    """
    try:
        payload = await request.json()
        
        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})
        
        logging.info(f"[PayPal Webhook] Received event: {event_type}")
        
        # Handle CHECKOUT.ORDER.COMPLETED - Order was fully paid
        if event_type == "CHECKOUT.ORDER.COMPLETED":
            paypal_order_id = resource.get("id")
            
            if paypal_order_id:
                # Find order in our database by PayPal order ID
                order = await db.orders.find_one(
                    {"paypal_order_id": paypal_order_id}, 
                    {"_id": 0}
                )
                
                if order:
                    internal_order_id = order.get("id")
                    
                    # Check if already processed
                    if order.get("payment_status") == "paid":
                        logging.info(f"[PayPal Webhook] Order {internal_order_id} already marked as paid")
                        return {"status": "already_processed"}
                    
                    # Extract payer info from webhook
                    payer = resource.get("payer", {})
                    payer_email = payer.get("email_address")
                    payer_id = payer.get("payer_id")
                    
                    # Update order status
                    await db.orders.update_one(
                        {"id": internal_order_id},
                        {
                            "$set": {
                                "payment_status": "paid",
                                "order_status": "processing",
                                "paypal_payer_id": payer_id,
                                "paypal_payer_email": payer_email,
                                "paid_at": datetime.now(timezone.utc).isoformat(),
                                "webhook_processed": True
                            }
                        }
                    )
                    
                    # Create payment transaction record if not exists
                    existing_transaction = await db.payment_transactions.find_one(
                        {"transaction_id": paypal_order_id}
                    )
                    
                    if not existing_transaction:
                        transaction = {
                            "id": str(uuid.uuid4()),
                            "order_id": internal_order_id,
                            "transaction_id": paypal_order_id,
                            "amount": float(order.get("total", 0)),
                            "currency": "CAD",
                            "payment_method": "paypal_api",
                            "payment_status": "paid",
                            "payer_id": payer_id,
                            "payer_email": payer_email,
                            "source": "webhook",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }
                        await db.payment_transactions.insert_one(transaction)
                    
                    # Trigger automated fulfillment chain
                    # 1. Deduct inventory
                    try:
                        await deduct_inventory_for_order(internal_order_id)
                        logging.info(f"[PayPal Webhook] Inventory deducted for order {internal_order_id}")
                    except Exception as inv_error:
                        logging.error(f"[PayPal Webhook] Inventory deduction failed: {inv_error}")
                    
                    # 2. Send confirmation email
                    customer_email = order.get("shipping_address", {}).get("email")
                    if customer_email:
                        try:
                            await send_order_confirmation_email(order, customer_email)
                        except Exception as email_error:
                            logging.error(f"[PayPal Webhook] Email failed: {email_error}")
                    
                    # 3. Broadcast to admin dashboard
                    await broadcast_admin_event("new_order", {
                        "order_id": internal_order_id,
                        "order_number": order.get("order_number", ""),
                        "total": order.get("total", 0),
                        "customer_email": customer_email,
                        "payment_method": "PayPal",
                        "source": "webhook"
                    })
                    
                    # 4. Auto-ship: Create shipping label automatically via FlagShip
                    try:
                        asyncio.create_task(process_auto_shipping(internal_order_id))
                        logging.info(f"[PayPal Webhook] Auto-shipping queued for order {internal_order_id}")
                    except Exception as ship_error:
                        logging.error(f"[PayPal Webhook] Auto-shipping failed: {ship_error}")
                    
                    logging.info(f"[PayPal Webhook] Order {internal_order_id} processed via webhook")
                    return {"status": "processed", "order_id": internal_order_id}
                else:
                    logging.warning(f"[PayPal Webhook] No order found for PayPal ID: {paypal_order_id}")
        
        # Handle PAYMENT.CAPTURE.COMPLETED
        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            capture_id = resource.get("id")
            logging.info(f"[PayPal Webhook] Capture completed: {capture_id}")
            # This is handled by the onApprove callback, just log it
            return {"status": "acknowledged"}
        
        # Handle PAYMENT.CAPTURE.DENIED / REFUNDED
        elif event_type in ["PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REFUNDED"]:
            capture_id = resource.get("id")
            logging.warning(f"[PayPal Webhook] Capture {event_type}: {capture_id}")
            # Update order status if needed
            return {"status": "acknowledged"}
        
        return {"status": "received", "event_type": event_type}
        
    except Exception as e:
        logging.error(f"[PayPal Webhook] Error: {e}")
        # Don't raise exception - return 200 to avoid PayPal retries
        return {"status": "error", "message": str(e)}


# ============= REVIEW ROUTES =============


@router.get("/reviews/{product_id}")
async def get_product_reviews(product_id: str):
    reviews = (
        await db.reviews.find(
            {"product_id": product_id, "is_approved": True}, {"_id": 0}
        )
        .sort("created_at", -1)
        .to_list(100)
    )
    return reviews


@router.post("/reviews")
async def create_review(review_data: ReviewCreate, request: Request):
    user = await require_auth(request)

    review = Review(
        product_id=review_data.product_id,
        rating=review_data.rating,
        title=review_data.title,
        comment=review_data.comment,
        images=review_data.images,
        user_id=user["id"],
        user_name=f"{user['first_name']} {user['last_name'][0]}.",
    )

    review_dict = review.model_dump()
    review_dict["created_at"] = review_dict["created_at"].isoformat()
    await db.reviews.insert_one(review_dict)

    # Update product average rating
    pipeline = [
        {"$match": {"product_id": review_data.product_id, "is_approved": True}},
        {
            "$group": {
                "_id": None,
                "avg_rating": {"$avg": "$rating"},
                "count": {"$sum": 1},
            }
        },
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    if result:
        await db.products.update_one(
            {"id": review_data.product_id},
            {
                "$set": {
                    "average_rating": round(result[0]["avg_rating"], 1),
                    "review_count": result[0]["count"],
                }
            },
        )

    # Send admin notification email (non-blocking)
    try:
        product = await db.products.find_one(
            {"id": review_data.product_id}, {"_id": 0, "name": 1}
        )
        product_name = (
            product.get("name", "Unknown Product") if product else "Unknown Product"
        )
        customer_name = f"{user.get('first_name', '')} {user.get('last_name', '')}"
        customer_email = user.get("email", "")

        # Fire and forget - don't wait for email
        asyncio.create_task(
            send_review_notification_email(
                review_dict, product_name, customer_name, customer_email
            )
        )
    except Exception as e:
        logging.error(f"Failed to queue review notification: {e}")

    return review


# ============= CALLBACK REQUESTS =============


@router.post("/callback-request")
async def create_callback_request(data: dict):
    """Customer requests a callback from admin"""
    callback = CallbackRequest(
        customer_name=data.get("customer_name", ""),
        phone=data.get("phone", ""),
        email=data.get("email"),
        preferred_time=data.get("preferred_time"),
        reason=data.get("reason"),
    )
    callback_dict = callback.model_dump()
    callback_dict["created_at"] = callback_dict["created_at"].isoformat()
    await db.callback_requests.insert_one(callback_dict)
    return {"message": "Callback request submitted successfully", "id": callback.id}


@router.get("/admin/callback-requests")
async def get_callback_requests(request: Request):
    """Admin gets all callback requests"""
    await require_admin(request)
    requests = (
        await db.callback_requests.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return requests


@router.put("/admin/callback-requests/{request_id}")
async def update_callback_request(request_id: str, data: dict, request: Request):
    """Admin updates a callback request status"""
    await require_admin(request)
    await db.callback_requests.update_one(
        {"id": request_id},
        {
            "$set": {
                "status": data.get("status", "pending"),
                "notes": data.get("notes", ""),
            }
        },
    )
    return {"message": "Callback request updated"}


# ============= TRANSLATION API =============

SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "French (Français)",
    "es": "Spanish (Español)",
    "hi": "Hindi (हिंदी)",
    "zh": "Chinese (中文)",
    "ar": "Arabic (العربية)",
    "pt": "Portuguese (Português)",
    "de": "German (Deutsch)",
    "ja": "Japanese (日本語)",
    "ko": "Korean (한국어)",
    "ru": "Russian (Русский)",
    "it": "Italian (Italiano)",
    "nl": "Dutch (Nederlands)",
    "tr": "Turkish (Türkçe)",
    "pl": "Polish (Polski)",
    "th": "Thai (ไทย)",
    "vi": "Vietnamese (Tiếng Việt)",
    "id": "Indonesian (Bahasa Indonesia)",
    "ms": "Malay (Bahasa Melayu)",
    "bn": "Bengali (বাংলা)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "mr": "Marathi (मराठी)",
    "gu": "Gujarati (ગુજરાતી)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "ur": "Urdu (اردو)",
    "fa": "Persian (فارسی)",
    "he": "Hebrew (עברית)",
    "sv": "Swedish (Svenska)",
    "no": "Norwegian (Norsk)",
    "da": "Danish (Dansk)",
    "fi": "Finnish (Suomi)",
    "el": "Greek (Ελληνικά)",
    "cs": "Czech (Čeština)",
    "ro": "Romanian (Română)",
    "hu": "Hungarian (Magyar)",
    "uk": "Ukrainian (Українська)",
}


@router.get("/languages")
async def get_supported_languages():
    """Get all supported languages"""
    return SUPPORTED_LANGUAGES


@router.post("/translate")
async def translate_text(data: dict):
    """Translate text to target language using AI"""
    text = data.get("text", "")
    target_lang = data.get("target_lang", "en")
    source_lang = data.get("source_lang", "auto")

    if not text.strip():
        return {"translated": text, "detected_lang": "en"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            return {"translated": text, "error": "No translation key configured"}
        
        chat = LlmChat(
            api_key=llm_key,
            session_id="translation",
            system_message="You are a professional translator.",
        ).with_model("openai", "gpt-4o")

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, "English")

        prompt = f"""Translate the following text to {lang_name}. 
Only provide the translation, nothing else. Keep the same tone and formatting.
If the text is already in {lang_name}, return it as-is.

Text to translate:
{text}"""

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        return {
            "translated": response.strip(),
            "target_lang": target_lang,
            "original": text,
        }
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return {"translated": text, "error": str(e)}


# Translation cache for performance
translation_cache = {}


@router.post("/translate/batch")
async def translate_batch(data: dict):
    """Translate multiple texts at once with caching"""
    texts = data.get("texts", [])
    target_lang = data.get("target_lang", "en")

    if not texts:
        return {"translations": []}

    # Check cache and separate cached vs uncached texts
    translations = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    for i, text in enumerate(texts):
        cache_key = f"{target_lang}:{text}"
        if cache_key in translation_cache:
            translations[i] = translation_cache[cache_key]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    # If all cached, return immediately
    if not uncached_texts:
        return {
            "translations": translations,
            "target_lang": target_lang,
            "cached": True,
        }

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not llm_key:
            # Fallback: return original texts if no API key
            return {"translations": texts, "target_lang": target_lang, "error": "No translation key configured"}
        
        chat = LlmChat(
            api_key=llm_key,
            session_id="translation-batch",
            system_message="You are a professional translator.",
        ).with_model("openai", "gpt-4o")

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, "English")

        # Combine texts with markers for batch translation
        combined = "\n---SPLIT---\n".join(uncached_texts)

        prompt = f"""Translate each of the following texts to {lang_name}. 
Keep them separated by ---SPLIT--- exactly as shown.
Only provide translations, nothing else.

Texts:
{combined}"""

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        new_translations = response.strip().split("---SPLIT---")
        new_translations = [t.strip() for t in new_translations]

        # Store in cache and fill results
        for i, idx in enumerate(uncached_indices):
            if i < len(new_translations):
                translated = new_translations[i]
                translations[idx] = translated
                # Cache the translation
                cache_key = f"{target_lang}:{uncached_texts[i]}"
                translation_cache[cache_key] = translated
                # Limit cache size to 5000 entries
                if len(translation_cache) > 5000:
                    # Remove oldest entries (simple FIFO)
                    keys_to_remove = list(translation_cache.keys())[:1000]
                    for k in keys_to_remove:
                        del translation_cache[k]
            else:
                translations[idx] = uncached_texts[i]

        return {"translations": translations, "target_lang": target_lang}
    except Exception as e:
        logging.error(f"Batch translation error: {e}")
        # Return original texts for uncached items
        for i, idx in enumerate(uncached_indices):
            translations[idx] = uncached_texts[i]
        return {"translations": translations, "error": str(e)}


@router.post("/translate/chat")
async def translate_chat_message(data: dict):
    """Translate chat message and detect language"""
    message = data.get("message", "")
    to_admin = data.get("to_admin", True)  # True = translate to English for admin

    if not message.strip():
        return {"translated": message, "detected_lang": "en"}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        chat = LlmChat(
            api_key=llm_key,
            session_id="translation-chat",
            system_message="You are a language detection and translation assistant.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        target = "English" if to_admin else "the customer's language"

        prompt = f"""Analyze this message and:
1. Detect the language
2. Translate to {target}

Message: {message}

Respond in JSON format only:
{{"detected_lang": "language_code", "detected_lang_name": "Language Name", "translated": "translated text"}}"""

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)

        # Parse JSON response
        import json

        try:
            result = json.loads(response.strip())
            return result
        except:
            return {
                "translated": message,
                "detected_lang": "en",
                "detected_lang_name": "English",
            }

    except Exception as e:
        logging.error(f"Chat translation error: {e}")
        return {"translated": message, "detected_lang": "en", "error": str(e)}


# ============= ADMIN CONNECTED ACCOUNTS =============

@router.get("/admin/connected-accounts")
async def get_connected_accounts(request: Request):
    """Get all connected external accounts for admin dashboard"""
    await require_admin(request)
    
    # Default accounts if none exist
    default_accounts = [
        {"id": "1", "name": "Stripe", "description": "Payments & Billing", "url": "https://dashboard.stripe.com", "color": "purple"},
        {"id": "2", "name": "Twilio", "description": "SMS & Phone Verification", "url": "https://console.twilio.com", "color": "red"},
        {"id": "3", "name": "Wix", "description": "Website Builder", "url": "https://manage.wix.com", "color": "blue"},
        {"id": "4", "name": "TD Bank", "description": "Payment Gateway", "url": "https://web.na.bambora.com", "color": "green"},
        {"id": "5", "name": "FlagShip", "description": "Shipping & Tracking", "url": "https://smartship.io/login", "color": "orange"},
        {"id": "6", "name": "Google Merchant", "description": "Product Listings", "url": "https://merchants.google.com", "color": "yellow"},
        {"id": "7", "name": "Bing Webmaster", "description": "SEO & Indexing", "url": "https://www.bing.com/webmasters", "color": "cyan"},
        {"id": "8", "name": "Search Console", "description": "Google SEO", "url": "https://search.google.com/search-console", "color": "sky"},
        {"id": "9", "name": "Resend", "description": "Email Service", "url": "https://resend.com/emails", "color": "pink"}
    ]
    
    # Get from database or return defaults
    accounts_doc = await db.admin_settings.find_one({"setting_type": "connected_accounts"}, {"_id": 0})
    
    if accounts_doc and accounts_doc.get("accounts"):
        return {"accounts": accounts_doc["accounts"]}
    
    # Initialize with defaults if not found
    await db.admin_settings.update_one(
        {"setting_type": "connected_accounts"},
        {"$set": {"accounts": default_accounts, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"accounts": default_accounts}


@router.post("/admin/connected-accounts")
async def save_connected_accounts(request: Request):
    """Save connected accounts to database"""
    await require_admin(request)
    
    data = await request.json()
    accounts = data.get("accounts", [])
    
    await db.admin_settings.update_one(
        {"setting_type": "connected_accounts"},
        {"$set": {"accounts": accounts, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"success": True, "message": "Connected accounts saved"}


@router.post("/admin/connected-accounts/add")
async def add_connected_account(request: Request):
    """Add a new connected account"""
    await require_admin(request)
    
    data = await request.json()
    new_account = {
        "id": str(uuid.uuid4()),
        "name": data.get("name"),
        "description": data.get("description", ""),
        "url": data.get("url"),
        "color": data.get("color", "blue")
    }
    
    if not new_account["name"] or not new_account["url"]:
        raise HTTPException(status_code=400, detail="Name and URL are required")
    
    # Get current accounts
    accounts_doc = await db.admin_settings.find_one({"setting_type": "connected_accounts"}, {"_id": 0})
    accounts = accounts_doc.get("accounts", []) if accounts_doc else []
    
    # Add new account
    accounts.append(new_account)
    
    # Save to database
    await db.admin_settings.update_one(
        {"setting_type": "connected_accounts"},
        {"$set": {"accounts": accounts, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"success": True, "account": new_account}


@router.put("/admin/connected-accounts/{account_id}")
async def update_connected_account(account_id: str, request: Request):
    """Update an existing connected account"""
    await require_admin(request)
    
    data = await request.json()
    
    # Get current accounts
    accounts_doc = await db.admin_settings.find_one({"setting_type": "connected_accounts"}, {"_id": 0})
    accounts = accounts_doc.get("accounts", []) if accounts_doc else []
    
    # Find and update the account
    updated = False
    for i, acc in enumerate(accounts):
        if acc["id"] == account_id:
            accounts[i] = {
                "id": account_id,
                "name": data.get("name", acc.get("name")),
                "description": data.get("description", acc.get("description", "")),
                "url": data.get("url", acc.get("url")),
                "color": data.get("color", acc.get("color", "blue"))
            }
            updated = True
            break
    
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Save to database
    await db.admin_settings.update_one(
        {"setting_type": "connected_accounts"},
        {"$set": {"accounts": accounts, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"success": True, "message": "Account updated"}


@router.delete("/admin/connected-accounts/{account_id}")
async def delete_connected_account(account_id: str, request: Request):
    """Delete a connected account"""
    await require_admin(request)
    
    # Get current accounts
    accounts_doc = await db.admin_settings.find_one({"setting_type": "connected_accounts"}, {"_id": 0})
    accounts = accounts_doc.get("accounts", []) if accounts_doc else []
    
    # Filter out the account to delete
    original_len = len(accounts)
    accounts = [acc for acc in accounts if acc["id"] != account_id]
    
    if len(accounts) == original_len:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Save to database
    await db.admin_settings.update_one(
        {"setting_type": "connected_accounts"},
        {"$set": {"accounts": accounts, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"success": True, "message": "Account deleted"}


