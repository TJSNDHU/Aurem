"""Regression tests for Round 11 security bugs (90–98) + P2 bugs (52, 54).

Bugs covered:
  52  WebSocket — accept JWT via first-message {"type":"auth"} (out of access logs)
  54  /leads/test-capture — admin-gated + env-gated
  90  connector router /connect, /fetch, /post — require admin
  91  video generation /generate, /status — require auth + daily quota
  92  Shopify OAuth callback — require HMAC + reject nonce mismatch (no skip)
  93  Shopify uninstall webhook — require X-Shopify-Hmac-Sha256
  94  aurem-keys list/revoke/usage — require JWT + business_id match
  95  Omnichannel SMS webhook — require Twilio sig; WhatsApp — require token
  96  Email inbound — fail closed when EMAIL_INBOUND_TOKEN unset
  97  Vapi voice webhook — derive tenant from JWT, never from payload
  98  Upload — reuse shared db handle, no new AsyncIOMotorClient per request
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))


# ─── Bug 90 ─────────────────────────────────────────────────────────
def test_bug90_connector_endpoints_require_admin():
    from routers import connector_router as c
    for fn in (c.connect_platform, c.fetch_data, c.post_data):
        src = inspect.getsource(fn)
        assert "_require_admin_connector" in src, (
            f"Bug 90: {fn.__name__} must call _require_admin_connector"
        )


# ─── Bug 91 ─────────────────────────────────────────────────────────
def test_bug91_video_generate_requires_auth_and_quota():
    from routers import video_generation_router as v
    gen_src = inspect.getsource(v.generate_video)
    assert "_verify_caller" in gen_src, "Bug 91: /generate must call _verify_caller"
    assert "_check_quota" in gen_src, "Bug 91: /generate must enforce per-user quota"
    status_src = inspect.getsource(v.get_video_status)
    assert "_verify_caller" in status_src, "Bug 91: /status must call _verify_caller"
    # Ownership check on /status
    assert "Not your video" in status_src or "created_by" in status_src


# ─── Bug 92 + 93 ────────────────────────────────────────────────────
def test_bug92_shopify_callback_requires_hmac_and_nonce():
    from routers import shopify_oauth_router as s
    src = inspect.getsource(s.oauth_callback)
    # Strip comments — they still mention the old pattern for context
    code_lines = [l for l in src.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    code_body = "\n".join(code_lines)
    # Old `if hmac_param and not` pattern must be gone from active code
    assert "hmac_param and not" not in code_body, (
        "Bug 92: old hmac-skip pattern still present in active code"
    )
    # New strict check
    assert "if not hmac_param or not _verify_hmac" in code_body
    # Nonce mismatch must raise, not silently continue
    assert "Continue anyway" not in code_body
    assert "Invalid OAuth state" in src


def test_bug93_shopify_uninstall_webhook_verifies_hmac():
    from routers import shopify_oauth_router as s
    src = inspect.getsource(s.app_uninstalled)
    assert "_verify_shopify_webhook_hmac" in src, (
        "Bug 93: uninstall webhook must verify HMAC"
    )
    assert "X-Shopify-Hmac-Sha256" in src


# ─── Bug 94 ─────────────────────────────────────────────────────────
def test_bug94_aurem_keys_require_business_owner():
    from routers import aurem_keys_router as k
    for fn in (k.list_api_keys, k.revoke_api_key, k.get_usage_stats):
        src = inspect.getsource(fn)
        assert "_verify_business_caller" in src, (
            f"Bug 94: {fn.__name__} must call _verify_business_caller"
        )


# ─── Bug 95 ─────────────────────────────────────────────────────────
def test_bug95_sms_webhook_verifies_twilio_signature():
    from routers import omnichannel_hub as o
    src = inspect.getsource(o.twilio_sms_webhook)
    assert "RequestValidator" in src, (
        "Bug 95: SMS webhook must use Twilio RequestValidator"
    )
    assert "X-Twilio-Signature" in src


def test_bug95_whatsapp_webhook_verifies_token():
    from routers import omnichannel_hub as o
    src = inspect.getsource(o.whatsapp_webhook)
    assert "WHAPI_WEBHOOK_TOKEN" in src, (
        "Bug 95: WhatsApp webhook must check WHAPI_WEBHOOK_TOKEN"
    )


# ─── Bug 96 ─────────────────────────────────────────────────────────
def test_bug96_email_inbound_fails_closed():
    from routers import email_inbound_router as e
    src = inspect.getsource(e._auth_ok)
    # The unguarded "return True" when token is unset must be gone
    assert "EMAIL_INBOUND_ALLOW_PUBLIC" in src, (
        "Bug 96: _auth_ok must require an explicit dev opt-in env"
    )


# ─── Bug 97 ─────────────────────────────────────────────────────────
def test_bug97_voice_webhook_derives_tenant_from_jwt():
    from routers import vapi_voice_router as vp
    src = inspect.getsource(vp.voice_event_handler)
    # Strip comments and rule out the new safe `token_payload` reference.
    code_lines = [l for l in src.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    code_body = "\n".join(code_lines).replace("token_payload.get", "TOKENPAYLOAD")
    # Active code must no longer assign tenant_id from the unverified request payload.
    assert 'payload.get("tenant_id")' not in code_body, (
        "Bug 97: active code still reads tenant_id from request payload"
    )
    assert "Authorization required" in src
    assert "token_payload" in src


# ─── Bug 98 ─────────────────────────────────────────────────────────
def test_bug98_upload_no_new_mongo_client_per_request():
    from routers import upload as u
    src = inspect.getsource(u.get_current_user_from_request)
    # No AsyncIOMotorClient instantiation inside the request handler
    assert "AsyncIOMotorClient(mongo_url)" not in src, (
        "Bug 98: upload still creates a new MongoClient per request"
    )
    assert "server.db" in src or "get_database" in src


# ─── P2 Bug 54 ─────────────────────────────────────────────────────
def test_bug54_test_capture_admin_gated_and_env_gated():
    from routers import leads_router as l
    src = inspect.getsource(l.test_lead_capture)
    assert "AUREM_TEST_ENDPOINTS_ENABLED" in src, (
        "Bug 54: /test-capture must be gated by env flag"
    )
    assert "verify_admin" in src, (
        "Bug 54: /test-capture must require admin auth"
    )


# ─── P2 Bug 52 ─────────────────────────────────────────────────────
def test_bug52_websocket_supports_first_message_auth():
    from routes import websocket as ws
    src = inspect.getsource(ws.websocket_endpoint)
    assert '"type": "auth"' in src or 'data.get("type") == "auth"' in src, (
        "Bug 52: WebSocket must support first-message {type:'auth'} JWT"
    )
    assert "auth_result" in src, (
        "Bug 52: WebSocket must reply with auth_result after first-message auth"
    )
