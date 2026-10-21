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
        send_order_confirmation_email,
        send_review_thank_you_email,
        send_shipping_notifications,
        send_shipping_update_email,
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)

_paypal_token_cache = {'token': None,'expires_at': 0}
async def get_paypal_access_token():
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
async def trigger_restock_notifications(*args,**kwargs): pass  # Stub: notifications not configured

# Environment variables — TODO: set these env vars in deployment configuration.
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL   = os.environ.get('SENDER_EMAIL',   'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

# Payment & messaging env vars — TODO: set BAMBORA_* env vars.
BAMBORA_MERCHANT_ID  = os.environ.get('BAMBORA_MERCHANT_ID', '')
BAMBORA_API_PASSCODE  = os.environ.get('BAMBORA_API_PASSCODE', '')
BAMBORA_API_URL      = os.environ.get('BAMBORA_API_URL',
                                      'https://api.na.bambora.com')

# PayPal — TODO: set PAYPAL_CLIENT_ID / PAYPAL_SECRET / PAYPAL_MODE env vars.
PAYPAL_CLIENT_ID     = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET       = os.environ.get('PAYPAL_SECRET', '')
PAYPAL_MODE         = os.environ.get('PAYPAL_MODE', 'sandbox')
_PAYPAL_SANDBOX_BASE   ='https://api-m.sandbox.paypal.com'
_PAYPAL_PRODUCTION_BASE='https://api-m.paypal.com'
def _resolve_paypal_base(mode=None):
    m=(mode or PAYPAL_MODE).lower()
return (_PAYPAL_PRODUCTION_BASE if m=='production' else _PAYPAL_SANDBOX_BASE)
def get_paypal_api_base():
return _resolve_paypal_base(PAYPAL_MODE)

# Twilio — TODO: set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN env vars.
TWILIO_ACCOUNT_SID=os.environ.get('TWILIO_ACCOUNT_SID','')
TWILIO_AUTH_TOKEN=os.environ.getenv ('TWILIO_AUTH_TOKEN','')


# Common imports from server.py scope -------------------------------------------------
bcrypt=__import__('bcrypt'); jwt=__import__('jwt')
try:
	import stripe as stripe_pkg; stripe=stripe_pkg		# alias kept for legacy refs below ──┐ except ImportError:													 │	stripe=None														 ├─ legacy alias ▶▶▶▶▶▶▶▶│																		 │																		 │																		 ▼																		▼																		▼																		▼																		▼																		▼																		▼																		▼																		▼																		▓▓▓▓▓▓▓▓																																				try:	from performance_patch	import limiter																except ImportErr