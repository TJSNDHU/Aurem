"""
Round 20 Security Sprint — Regression Suite
============================================
Verifies the R20 fixes (Bugs 165-171) shipped in this sprint.
"""
from __future__ import annotations

import os
import re
import time
import jwt as pyjwt
import pytest
import requests

# Load JWT_SECRET from backend .env if not in environment
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


def _put(path: str, **kw):
    return requests.put(f"{BACKEND}{path}", timeout=15, **kw)


def _customer_token(email: str = "customer@example.com") -> str:
    secret = os.environ.get("JWT_SECRET") or "test-secret"
    return pyjwt.encode(
        {"email": email, "role": "customer", "user_id": "u1",
         "exp": int(time.time()) + 3600},
        secret, algorithm="HS256",
    )


def _strip_comments(src: str) -> str:
    out = re.sub(r'#.*', '', src)
    out = re.sub(r'"""[\s\S]*?"""', '', out)
    out = re.sub(r"'''[\s\S]*?'''", '', out)
    return out


# ─── Bug 165 — infra_settings_router admin-only ─────────────────────────────
def test_bug_165_infra_get_rejects_customer_token():
    r = _get("/api/settings/infrastructure",
             headers={"Authorization": f"Bearer {_customer_token()}"})
    assert r.status_code in (401, 403, 404)


def test_bug_165_infra_put_rejects_customer_token():
    r = _put("/api/settings/infrastructure",
             headers={"Authorization": f"Bearer {_customer_token()}"},
             json={"redis_url": "redis://attacker.evil:6379"})
    assert r.status_code in (401, 403, 404)


def test_bug_165_no_email_bypass_in_source():
    code = _strip_comments(open("/app/backend/routers/infra_settings_router.py").read())
    assert 'or payload.get("email")' not in code


# ─── Bug 166 — ooda_loop_router admin-only ─────────────────────────────────
def test_bug_166_ooda_execute_requires_admin():
    r = _post("/api/ooda/execute", json={"cycle_id": "weekly_audit"})
    assert r.status_code in (401, 403, 404)


def test_bug_166_ooda_execute_rejects_customer_token():
    r = _post("/api/ooda/execute",
              headers={"Authorization": f"Bearer {_customer_token()}"},
              json={"cycle_id": "weekly_audit"})
    assert r.status_code in (401, 403, 404)


def test_bug_166_ooda_schedule_requires_admin():
    r = _post("/api/ooda/schedule?cycle_id=weekly_audit&cron_expression=0 9 * * *")
    assert r.status_code in (401, 403, 404)


# ─── Bug 167 — chat_widget get_client_ip prefers CF-Connecting-IP ───────────
def test_bug_167_get_client_ip_trusts_only_cf_header():
    src = open("/app/backend/routes/chat_widget_routes.py").read()
    func = src.split("def get_client_ip")[1].split("def ")[0]
    assert "cf-connecting-ip" in func.lower()
    # Only consult X-Forwarded-For when explicit opt-in env is set.
    assert "AUREM_TRUST_XFF" in func


# ─── Bug 168 — failed_logins persisted to MongoDB ───────────────────────────
def test_bug_168_failed_logins_persisted_to_mongo():
    src = open("/app/backend/routes/auth.py").read()
    assert "failed_login_attempts" in src
    assert "_ensure_failed_login_index" in src
    # record_failed_login must write to Mongo.
    rec = src.split("def record_failed_login")[1].split("def ")[0]
    assert "failed_login_attempts" in rec or "insert_one" in rec
    # clear_failed_logins must clear Mongo too.
    clr = src.split("def clear_failed_logins")[1].split("def ")[0]
    assert "delete_many" in clr or "failed_login_attempts" in clr


# ─── Bug 169 — v2v web-call rate-limited ────────────────────────────────────
def test_bug_169_v2v_web_call_has_rate_limit_guard():
    src = open("/app/backend/routers/v2v_stream_engine.py").read()
    body = src.split("async def create_web_call")[1].split("async def ")[0]
    assert "is_rate_limited" in body or "rate_limit" in body.lower()
    assert "v2v_web_call" in body


# ─── Bug 170 — service_gate refuses default salt ────────────────────────────
def test_bug_170_service_gate_refuses_default_salt():
    src = open("/app/backend/utils/service_gate.py").read()
    body = src.split("def _hash_bin")[1].split("\ndef ")[0]
    # Production must refuse to use the default salt
    assert "AUREM_ENV" in body and "production" in body
    # Default fallback string no longer used as the active salt
    assert 'os.environ.get("ADMIN_ORA_HASH_SALT", "aurem-default-salt")' not in src


# ─── Bug 171 — verify_exp:False removed across 5 routers ────────────────────
@pytest.mark.parametrize("path", [
    "/app/backend/routers/agents_router.py",
    "/app/backend/routers/agent_board_router.py",
    "/app/backend/routers/v2v_stream_engine.py",
    "/app/backend/routers/repair_checkout_router.py",
    "/app/backend/routers/sentinel_router.py",
])
def test_bug_171_verify_exp_false_removed(path):
    src = open(path).read()
    assert '"verify_exp": False' not in src, f"{path} still bypasses JWT expiry"
    assert "'verify_exp': False" not in src
