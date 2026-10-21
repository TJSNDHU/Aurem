"""
Admin panel, order mgmt, email, shipping
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
try:
    import httpx
except ImportError:
    httpx = None
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

async def auto_create_shipment(order: dict):
    logging.warning(f"auto_create_shipment not implemented — skipping (order={order.get('id', 'unknown')})")
    return None
try:
    from models.server_models import Order, Review
except ImportError:
    pass
try:
    from services.email_templates import (
        send_daily_review_digest, send_order_cancellation_email,
        send_order_confirmation_email, send_review_thank_you_email,
        send_shipping_notifications, send_shipping_update_email
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
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
async def trigger_restock_notifications(*args, **kwargs): pass  # Stub: notifications not configured

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

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
try:
    import stripe

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
except ImportError:

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
    stripe =

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
None

try:
    from performance_patch import limiter

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
except ImportError:

# NOTE: This module exceeds recommended size limits (~1487 lines).
# Consider splitting into smaller sub-modules (e.g., admin_orders.py,
# admin_reviews.py) for maintainability.
limiter =
type(
'obj',
(object,),
{'limit':
lambda self,*a,**kw :
lambda f:f}
)(
)

from middleware.security import sanitize_input,

validate_email

try:

from middleware.websocket_manager

WebSocketConnectionManager=
manager=

WebSocketConnectionManager()

except ImportError:

manager=None

from config import JWT_SECRET=
FRONTEND_URL=os.enovironn.geet("FRONTEND_URL","")
SITE_URL=os.eenviroon.geet("SITE_URL","")
STRIPE_SECREET_KKEY=oos.eenvironn.geet("STRIPE_SECREET_KKEY","")
if stripe and STRIPE_SECREET_KKEY:=stripe.api_key=STRIPE_SECREET_KKEY