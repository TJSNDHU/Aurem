"""
Round 21 + 22 Security Sprint — Regression Suite
=================================================
Verifies fixes for Bugs 172-185.
"""
from __future__ import annotations

import os
import re
import time
import jwt as pyjwt
import pytest
import requests

# Load JWT_SECRET from backend .env
if not os.environ.get("JWT_SECRET"):
    try:
        for line in open("/app/backend/.env"):
            if line.strip().startswith("JWT_SECRET="):
                os.environ["JWT_SECRET"] = line.split("=", 1)[1].strip()
                break
    except Exception:
        pass

BACKEND = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[-1].splitlines()[0]
).strip()


def _post(path: str, **kw):
    return requests.post(f"{BACKEND}{path}", timeout=15, **kw)


def _get(path: str, **kw):
    return requests.get(f"{BACKEND}{path}", timeout=15, **kw)


def _delete(path: str, **kw):
    return requests.delete(f"{BACKEND}{path}", timeout=15, **kw)


def _customer_token() -> str:
    secret = os.environ.get("JWT_SECRET") or "test-secret"
    return pyjwt.encode(
        {"email": "customer@example.com", "role": "customer", "user_id": "u1",
         "exp": int(time.time()) + 3600},
        secret, algorithm="HS256",
    )


def _strip_comments(src: str) -> str:
    out = re.sub(r'#.*', '', src)
    out = re.sub(r'"""[\s\S]*?"""', '', out)
    out = re.sub(r"'''[\s\S]*?'''", '', out)
    return out


# ─── Bug 172 — diagnostic_router cleaned up ─────────────────────────────────
def test_bug_172_no_email_bypass_or_hardcoded_secret():
    code = _strip_comments(open("/app/backend/routers/diagnostic_router.py").read())
    assert 'or payload.get("email")' not in code
    assert "aurem-secret-key" not in code


# ─── Bug 173 — sms_admin enforces expiry + no hardcoded founder ─────────────
def test_bug_173_sms_admin_no_verify_exp_false():
    src = open("/app/backend/routers/sms_admin_router.py").read()
    assert '"verify_exp": False' not in src


def test_bug_173_sms_admin_no_hardcoded_founder_email():
    code = _strip_comments(open("/app/backend/routers/sms_admin_router.py").read())
    assert '"teji.ss1986@gmail.com"' not in code


# ─── Bug 174 — vector_search /index admin-only ──────────────────────────────
def test_bug_174_vector_index_rejects_anon():
    r = _post("/api/vector/index",
              json={"platform": "reddit", "data": [{"title": "x", "text": "y"}]})
    assert r.status_code in (401, 403, 404)


def test_bug_174_vector_index_rejects_customer():
    r = _post("/api/vector/index",
              headers={"Authorization": f"Bearer {_customer_token()}"},
              json={"platform": "reddit", "data": [{"title": "x", "text": "y"}]})
    assert r.status_code in (401, 403, 404)


# ─── Bug 175 — 4 files refuse default encryption key in production ──────────
@pytest.mark.parametrize("path", [
    "/app/backend/routers/nexus_router.py",
    "/app/backend/utils/vault_credentials.py",
    "/app/backend/routers/ai_repair_router.py",
])
def test_bug_175_no_default_encryption_key(path):
    src = open(path).read()
    # The active runtime line is now wrapped in _load_aurem_encryption_key().
    assert 'os.environ.get("AUREM_ENCRYPTION_KEY", "aurem32characterencryptionkey!")' not in src
    assert "_load_aurem_encryption_key" in src
    # Production guard present
    body = src.split("def _load_aurem_encryption_key")[1].split("\ndef ")[0]
    assert "AUREM_ENV" in body and "production" in body


# ─── Bug 176 — appointment endpoints admin-only ─────────────────────────────
def test_bug_176_book_rejects_anon():
    r = _post("/api/appointments/book",
              json={"customer_name": "x", "customer_email": "a@b.co",
                    "customer_phone": "1234", "appointment_type": "discovery",
                    "preferred_date": "2026-01-01", "preferred_time": "10:00"})
    assert r.status_code in (401, 403, 404)


def test_bug_176_delete_rejects_anon():
    r = _delete("/api/appointments/appt_deadbeefcafef00d")
    assert r.status_code in (401, 403, 404)


def test_bug_176_customer_lookup_rejects_anon():
    r = _get("/api/appointments/customer/victim@example.com")
    assert r.status_code in (401, 403, 404)


# ─── Bug 177 — extension_leads bulk + delete admin-only ─────────────────────
def test_bug_177_bulk_rejects_anon():
    r = _post("/api/extension/leads/bulk",
              json={"leads": [{"name": "x"}]})
    assert r.status_code in (401, 403, 404)


def test_bug_177_bulk_rejects_customer():
    r = _post("/api/extension/leads/bulk",
              headers={"Authorization": f"Bearer {_customer_token()}"},
              json={"leads": [{"name": "x"}]})
    assert r.status_code in (401, 403, 404)


def test_bug_177_lead_delete_rejects_anon():
    r = _delete("/api/extension/leads/anything")
    assert r.status_code in (401, 403, 404)


# ─── Bug 178 — guardrail_proxy no hardcoded admin phone ─────────────────────
def test_bug_178_no_hardcoded_admin_phone():
    code = _strip_comments(open("/app/backend/services/guardrail_proxy.py").read())
    # The literal must not appear as a fallback constant anymore.
    assert '"12265017777"' not in code
    assert "_resolve_admin_phone" in code


# ─── Bug 179 — GDPR delete requires signed token ────────────────────────────
def test_bug_179_gdpr_delete_requires_token():
    r = _get("/api/customer/delete-my-data?email=victim@example.com")
    # 422 = pydantic Query validation rejecting missing token (FastAPI)
    # 401 = handler raised invalid token
    # 404 = router not loaded in LEAN mode
    assert r.status_code in (401, 422, 404)


def test_bug_179_gdpr_post_requires_token():
    r = _post("/api/customer/delete-my-data",
              json={"email": "victim@example.com", "confirmation": "DELETE MY DATA"})
    assert r.status_code in (401, 422, 404)


def test_bug_179_request_deletion_endpoint_exists():
    src = open("/app/backend/routes/data_security_routes.py").read()
    assert "request-deletion" in src
    assert '"type": "gdpr_delete"' in src
    # Generic response — must not leak whether email exists
    assert "If the email exists" in src


# ─── Bug 180 — aurem_admin /sync admin-only ─────────────────────────────────
def test_bug_180_aurem_sync_rejects_anon():
    r = _post("/api/aurem/admin/sync")
    assert r.status_code in (401, 403, 404)


def test_bug_180_aurem_sync_rejects_customer():
    r = _post("/api/aurem/admin/sync",
              headers={"Authorization": f"Bearer {_customer_token()}"})
    assert r.status_code in (401, 403, 404)


# ─── Bug 181 — universal_connector Shopify/WC HMAC ──────────────────────────
def test_bug_181_universal_shopify_hmac_check_present():
    src = open("/app/backend/routers/universal_connector_router.py").read()
    body = src.split("async def receive_webhook")[1].split("async def ")[0]
    assert 'platform == "shopify"' in body
    assert "X-Shopify-Hmac-Sha256" in body or "x-shopify-hmac-sha256" in body
    assert 'platform == "woocommerce"' in body
    assert "x-wc-webhook-signature" in body


# ─── Bug 182 — seo /scan + /outreach admin-only ─────────────────────────────
def test_bug_182_seo_scan_rejects_anon():
    r = _post("/api/seo/unlinked/scan",
              json={"business_name": "X", "website_url": "https://x.com"})
    assert r.status_code in (401, 403, 404)


def test_bug_182_seo_outreach_rejects_anon():
    r = _post("/api/seo/unlinked/outreach",
              json={"mention_id": "x"})
    assert r.status_code in (401, 403, 404)


# ─── Bug 183 — z_image /generate + /enhance-prompt admin-only ───────────────
def test_bug_183_zimage_generate_rejects_anon():
    r = _post("/api/zimg/generate",
              json={"prompt": "a cat"})
    assert r.status_code in (401, 403, 404)


def test_bug_183_zimage_enhance_rejects_anon():
    r = _post("/api/zimg/enhance-prompt", params={"prompt": "a cat"})
    assert r.status_code in (401, 403, 404)


# ─── Bug 184 — live_sync broadcast + sync admin-only ────────────────────────
def test_bug_184_live_broadcast_rejects_anon():
    r = _post("/api/live/broadcast",
              json={"resource": "product", "action": "delete"})
    assert r.status_code in (401, 403, 404)


def test_bug_184_live_sync_rejects_anon():
    r = _post("/api/live/sync",
              json={"user_id": "victim", "state": {}})
    assert r.status_code in (401, 403, 404)


# ─── Bug 185 — smart_search /switch admin-only ──────────────────────────────
def test_bug_185_search_switch_rejects_anon():
    r = _post("/api/search/switch?engine=duckduckgo")
    assert r.status_code in (401, 403, 404)


def test_bug_185_search_switch_rejects_customer():
    r = _post("/api/search/switch?engine=duckduckgo",
              headers={"Authorization": f"Bearer {_customer_token()}"})
    assert r.status_code in (401, 403, 404)
